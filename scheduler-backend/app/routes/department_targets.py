from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.department_target import DepartmentTarget

from app.schemas.department_target import DepartmentTargetCreate
from app.schemas.department_target import DepartmentTargetResponse

router = APIRouter(
    prefix="/department-targets",
    tags=["Department Targets"]
)


@router.get("/", response_model=list[DepartmentTargetResponse])
def get_department_targets(db: Session = Depends(get_db)):

    return db.query(DepartmentTarget).all()


@router.get("/{target_id}", response_model=DepartmentTargetResponse)
def get_department_target(target_id: int, db: Session = Depends(get_db)):

    target = db.query(DepartmentTarget).filter(DepartmentTarget.target_id == target_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="Department target not found")

    return target


@router.post("/", response_model=DepartmentTargetResponse)
def create_department_target(department_target: DepartmentTargetCreate,
                              db: Session = Depends(get_db)):

    db_target = DepartmentTarget(**department_target.model_dump())

    db.add(db_target)
    db.commit()
    db.refresh(db_target)

    return db_target


@router.put("/{target_id}", response_model=DepartmentTargetResponse)
def update_department_target(target_id: int,
                              department_target: DepartmentTargetCreate,
                              db: Session = Depends(get_db)):

    db_target = db.query(DepartmentTarget).filter(DepartmentTarget.target_id == target_id).first()

    if not db_target:
        raise HTTPException(status_code=404, detail="Department target not found")

    for field, value in department_target.model_dump().items():
        setattr(db_target, field, value)

    db.commit()
    db.refresh(db_target)

    return db_target


@router.delete("/{target_id}", status_code=204)
def delete_department_target(target_id: int, db: Session = Depends(get_db)):

    db_target = db.query(DepartmentTarget).filter(DepartmentTarget.target_id == target_id).first()

    if not db_target:
        raise HTTPException(status_code=404, detail="Department target not found")

    db.delete(db_target)
    db.commit()
