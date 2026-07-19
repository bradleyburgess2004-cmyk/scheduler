from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.time_off_request import TimeOffRequest

from app.schemas.time_off_request import TimeOffRequestCreate
from app.schemas.time_off_request import TimeOffRequestResponse

router = APIRouter(
    prefix="/time-off-requests",
    tags=["Time Off Requests"]
)


@router.get("/", response_model=list[TimeOffRequestResponse])
def get_time_off_requests(db: Session = Depends(get_db)):

    return db.query(TimeOffRequest).all()


@router.get("/{request_id}", response_model=TimeOffRequestResponse)
def get_time_off_request(request_id: int, db: Session = Depends(get_db)):

    request = db.query(TimeOffRequest).filter(TimeOffRequest.request_id == request_id).first()

    if not request:
        raise HTTPException(status_code=404, detail="Time off request not found")

    return request


@router.post("/", response_model=TimeOffRequestResponse)
def create_time_off_request(time_off_request: TimeOffRequestCreate,
                             db: Session = Depends(get_db)):

    db_request = TimeOffRequest(**time_off_request.model_dump())

    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    return db_request


@router.put("/{request_id}", response_model=TimeOffRequestResponse)
def update_time_off_request(request_id: int,
                             time_off_request: TimeOffRequestCreate,
                             db: Session = Depends(get_db)):

    db_request = db.query(TimeOffRequest).filter(TimeOffRequest.request_id == request_id).first()

    if not db_request:
        raise HTTPException(status_code=404, detail="Time off request not found")

    for field, value in time_off_request.model_dump().items():
        setattr(db_request, field, value)

    db.commit()
    db.refresh(db_request)

    return db_request


@router.delete("/{request_id}", status_code=204)
def delete_time_off_request(request_id: int, db: Session = Depends(get_db)):

    db_request = db.query(TimeOffRequest).filter(TimeOffRequest.request_id == request_id).first()

    if not db_request:
        raise HTTPException(status_code=404, detail="Time off request not found")

    db.delete(db_request)
    db.commit()
