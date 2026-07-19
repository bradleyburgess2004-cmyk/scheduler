from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.shift_template import ShiftTemplate

from app.schemas.shift_template import ShiftTemplateCreate
from app.schemas.shift_template import ShiftTemplateResponse

router = APIRouter(
    prefix="/shift-templates",
    tags=["Shift Templates"]
)


@router.get("/", response_model=list[ShiftTemplateResponse])
def get_shift_templates(db: Session = Depends(get_db)):

    return db.query(ShiftTemplate).all()


@router.get("/{template_id}", response_model=ShiftTemplateResponse)
def get_shift_template(template_id: int, db: Session = Depends(get_db)):

    template = db.query(ShiftTemplate).filter(ShiftTemplate.template_id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Shift template not found")

    return template


@router.post("/", response_model=ShiftTemplateResponse)
def create_shift_template(shift_template: ShiftTemplateCreate,
                           db: Session = Depends(get_db)):

    db_template = ShiftTemplate(**shift_template.model_dump())

    db.add(db_template)
    db.commit()
    db.refresh(db_template)

    return db_template


@router.put("/{template_id}", response_model=ShiftTemplateResponse)
def update_shift_template(template_id: int,
                           shift_template: ShiftTemplateCreate,
                           db: Session = Depends(get_db)):

    db_template = db.query(ShiftTemplate).filter(ShiftTemplate.template_id == template_id).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Shift template not found")

    for field, value in shift_template.model_dump().items():
        setattr(db_template, field, value)

    db.commit()
    db.refresh(db_template)

    return db_template


@router.delete("/{template_id}", status_code=204)
def delete_shift_template(template_id: int, db: Session = Depends(get_db)):

    db_template = db.query(ShiftTemplate).filter(ShiftTemplate.template_id == template_id).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Shift template not found")

    db.delete(db_template)
    db.commit()
