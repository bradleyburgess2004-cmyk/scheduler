from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.shift import Shift

from app.schemas.shift import ShiftCreate
from app.schemas.shift import ShiftResponse

router = APIRouter(
    prefix="/shifts",
    tags=["Shifts"]
)


@router.get("/", response_model=list[ShiftResponse])
def get_shifts(db: Session = Depends(get_db)):

    return db.query(Shift).all()


@router.get("/{shift_id}", response_model=ShiftResponse)
def get_shift(shift_id: int, db: Session = Depends(get_db)):

    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()

    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    return shift


@router.post("/", response_model=ShiftResponse)
def create_shift(shift: ShiftCreate, db: Session = Depends(get_db)):

    db_shift = Shift(**shift.model_dump())

    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)

    return db_shift


@router.put("/{shift_id}", response_model=ShiftResponse)
def update_shift(shift_id: int, shift: ShiftCreate, db: Session = Depends(get_db)):

    db_shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()

    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    for field, value in shift.model_dump().items():
        setattr(db_shift, field, value)

    db.commit()
    db.refresh(db_shift)

    return db_shift


@router.delete("/{shift_id}", status_code=204)
def delete_shift(shift_id: int, db: Session = Depends(get_db)):

    db_shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()

    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    db.delete(db_shift)
    db.commit()
