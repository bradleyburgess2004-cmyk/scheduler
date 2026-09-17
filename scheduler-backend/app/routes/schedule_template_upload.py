from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant
from app.models.schedule_template import ScheduleTemplate

from app.schemas.schedule_template import DAY_NAMES
from app.schemas.schedule_template import ScheduleTemplateEntryOut
from app.schemas.schedule_template import ScheduleTemplateParseResponse
from app.schemas.schedule_template import ScheduleTemplateSaveRequest
from app.schemas.schedule_template import ScheduleTemplateSaveResponse
from app.schemas.schedule_template import ScheduleTemplateSummary

from app.services.schedule_template_parser import parse_schedule_template_csv
from app.services.schedule_template_parser import save_schedule_template

router = APIRouter(
    prefix="/restaurants",
    tags=["Schedule Template"],
)


def _get_restaurant_or_404(restaurant_id: int, db: Session) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.post("/{restaurant_id}/schedule-templates/parse", response_model=ScheduleTemplateParseResponse)
async def parse_schedule_template(
    restaurant_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parses a wide-format schedule-template CSV (rows = employees,
    columns = days of week, cells = 'HH:MM-HH:MM' or blank/OFF) for
    review. Read-only -- never writes to the database; the caller
    reviews (and can edit) the result and POSTs it back to
    /schedule-templates to actually save it."""

    _get_restaurant_or_404(restaurant_id, db)

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV")

    try:
        return parse_schedule_template_csv(db, restaurant_id, text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Could not parse schedule template file: {e}")


@router.post("/{restaurant_id}/schedule-templates", response_model=ScheduleTemplateSaveResponse)
def create_schedule_template(
    restaurant_id: int,
    body: ScheduleTemplateSaveRequest,
    db: Session = Depends(get_db),
):
    """Saves the (possibly user-reviewed/edited) parsed entries as a
    named ScheduleTemplate. Entries with no resolved employee_id are
    skipped and counted, never saved."""

    _get_restaurant_or_404(restaurant_id, db)

    entries_skipped_unmatched = sum(1 for e in body.entries if e.employee_id is None)

    template = save_schedule_template(db, restaurant_id, body.name, body.entries)
    db.commit()

    return ScheduleTemplateSaveResponse(
        template_id=template.template_id,
        name=template.name,
        entries_saved=len(template.entries),
        entries_skipped_unmatched=entries_skipped_unmatched,
    )


@router.get("/{restaurant_id}/schedule-templates", response_model=list[ScheduleTemplateSummary])
def list_schedule_templates(
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    _get_restaurant_or_404(restaurant_id, db)

    templates = (
        db.query(ScheduleTemplate)
        .filter(ScheduleTemplate.restaurant_id == restaurant_id)
        .order_by(ScheduleTemplate.created_at.desc())
        .all()
    )
    return [
        ScheduleTemplateSummary(
            template_id=t.template_id,
            name=t.name,
            created_at=t.created_at,
            entry_count=len(t.entries),
        )
        for t in templates
    ]


@router.get("/{restaurant_id}/schedule-templates/{template_id}", response_model=list[ScheduleTemplateEntryOut])
def get_schedule_template(
    restaurant_id: int,
    template_id: int,
    db: Session = Depends(get_db),
):
    _get_restaurant_or_404(restaurant_id, db)

    template = (
        db.query(ScheduleTemplate)
        .filter(
            ScheduleTemplate.restaurant_id == restaurant_id,
            ScheduleTemplate.template_id == template_id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Schedule template not found")

    return [
        ScheduleTemplateEntryOut(
            entry_id=e.entry_id,
            raw_employee_label=f"{e.employee.first_name} {e.employee.last_name}",
            employee_id=e.employee_id,
            employee_name=f"{e.employee.first_name} {e.employee.last_name}",
            day_of_week=e.day_of_week,
            day_name=DAY_NAMES[e.day_of_week],
            start_time=e.start_time,
            end_time=e.end_time,
        )
        for e in template.entries
    ]


@router.delete("/{restaurant_id}/schedule-templates/{template_id}", status_code=204)
def delete_schedule_template(
    restaurant_id: int,
    template_id: int,
    db: Session = Depends(get_db),
):
    _get_restaurant_or_404(restaurant_id, db)

    template = (
        db.query(ScheduleTemplate)
        .filter(
            ScheduleTemplate.restaurant_id == restaurant_id,
            ScheduleTemplate.template_id == template_id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Schedule template not found")

    db.delete(template)
    db.commit()
