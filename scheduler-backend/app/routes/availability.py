from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.availability import Availability

from app.schemas.availability import AvailabilityCreate
from app.schemas.availability import AvailabilityResponse

router = APIRouter(
    prefix="/availability",
    tags=["Availability"]
)


@router.get("/", response_model=list[AvailabilityResponse])
def get_availability_records(db: Session = Depends(get_db)):

    return db.query(Availability).all()


@router.get("/{availability_id}", response_model=AvailabilityResponse)
def get_availability(availability_id: int, db: Session = Depends(get_db)):

    availability = db.query(Availability).filter(Availability.availability_id == availability_id).first()

    if not availability:
        raise HTTPException(status_code=404, detail="Availability record not found")

    return availability


@router.post("/", response_model=AvailabilityResponse)
def create_availability(availability: AvailabilityCreate,
                         db: Session = Depends(get_db)):

    db_availability = Availability(**availability.model_dump())

    db.add(db_availability)
    db.commit()
    db.refresh(db_availability)

    return db_availability


@router.put("/{availability_id}", response_model=AvailabilityResponse)
def update_availability(availability_id: int,
                         availability: AvailabilityCreate,
                         db: Session = Depends(get_db)):

    db_availability = db.query(Availability).filter(Availability.availability_id == availability_id).first()

    if not db_availability:
        raise HTTPException(status_code=404, detail="Availability record not found")

    for field, value in availability.model_dump().items():
        setattr(db_availability, field, value)

    db.commit()
    db.refresh(db_availability)

    return db_availability


@router.delete("/{availability_id}", status_code=204)
def delete_availability(availability_id: int, db: Session = Depends(get_db)):

    db_availability = db.query(Availability).filter(Availability.availability_id == availability_id).first()

    if not db_availability:
        raise HTTPException(status_code=404, detail="Availability record not found")

    db.delete(db_availability)
    db.commit()
