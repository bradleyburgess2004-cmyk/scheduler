from datetime import timedelta

import anthropic

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant

from app.schemas.time_off import TimeOffApplyRequest
from app.schemas.time_off import TimeOffApplyResponse
from app.schemas.time_off import TimeOffParseResponse

from app.services.time_off_parser import apply_time_off_day
from app.services.time_off_parser import parse_time_off_report

router = APIRouter(
    prefix="/restaurants",
    tags=["Time Off Upload"],
)


def _get_restaurant_or_404(restaurant_id: int, db: Session) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.post("/{restaurant_id}/time-off/parse", response_model=TimeOffParseResponse)
async def parse_time_off(
    restaurant_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parses a raw, copy-pasted 'Time Off & Request Report' text export
    into structured records for review. Read-only -- never writes to
    the database; the caller reviews the result and POSTs it back to
    /time-off/apply to actually apply it."""

    _get_restaurant_or_404(restaurant_id, db)

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        records = parse_time_off_report(db, restaurant_id, text)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=502,
            detail="Couldn't authenticate with Anthropic -- check that ANTHROPIC_API_KEY is set "
                   "correctly and the backend server has been restarted since it was added.",
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"The report parser is unavailable right now: {exc}")

    return TimeOffParseResponse(records=records)


@router.post("/{restaurant_id}/time-off/apply", response_model=TimeOffApplyResponse)
def apply_time_off(
    restaurant_id: int,
    body: TimeOffApplyRequest,
    db: Session = Depends(get_db),
):
    """Applies the (possibly user-reviewed/edited) parsed records:
    every request with status == 'Approved' and a resolved employee_id
    gets each date in its range marked unavailable. Denied/Canceled/
    Pending requests and unmatched employee names are skipped and
    counted, never applied."""

    _get_restaurant_or_404(restaurant_id, db)

    days_blocked = 0
    requests_applied = 0
    requests_skipped_not_approved = 0
    requests_skipped_unmatched = 0

    for record in body.records:
        if record.status != "Approved":
            requests_skipped_not_approved += 1
            continue
        if record.employee_id is None:
            requests_skipped_unmatched += 1
            continue

        d = record.start_date
        while d <= record.end_date:
            apply_time_off_day(db, record.employee_id, d)
            days_blocked += 1
            d += timedelta(days=1)
        requests_applied += 1

    db.commit()

    return TimeOffApplyResponse(
        days_blocked=days_blocked,
        requests_applied=requests_applied,
        requests_skipped_not_approved=requests_skipped_not_approved,
        requests_skipped_unmatched=requests_skipped_unmatched,
    )
