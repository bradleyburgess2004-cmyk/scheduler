from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.employee_skill import EmployeeSkill

from app.schemas.employee_skill import EmployeeSkillCreate
from app.schemas.employee_skill import EmployeeSkillResponse

router = APIRouter(
    prefix="/employee-skills",
    tags=["Employee Skills"]
)


@router.get("/", response_model=list[EmployeeSkillResponse])
def get_employee_skills(db: Session = Depends(get_db)):

    return db.query(EmployeeSkill).all()


@router.get("/{employee_id}/{skill_id}", response_model=EmployeeSkillResponse)
def get_employee_skill(employee_id: int, skill_id: int, db: Session = Depends(get_db)):

    record = db.query(EmployeeSkill).filter(
        EmployeeSkill.employee_id == employee_id,
        EmployeeSkill.skill_id == skill_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Employee skill not found")

    return record


@router.post("/", response_model=EmployeeSkillResponse)
def create_employee_skill(employee_skill: EmployeeSkillCreate,
                           db: Session = Depends(get_db)):

    db_employee_skill = EmployeeSkill(**employee_skill.model_dump())

    db.add(db_employee_skill)
    db.commit()
    db.refresh(db_employee_skill)

    return db_employee_skill


@router.delete("/{employee_id}/{skill_id}", status_code=204)
def delete_employee_skill(employee_id: int, skill_id: int, db: Session = Depends(get_db)):

    record = db.query(EmployeeSkill).filter(
        EmployeeSkill.employee_id == employee_id,
        EmployeeSkill.skill_id == skill_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Employee skill not found")

    db.delete(record)
    db.commit()
