from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.employee import Employee
from app.models.assignment import Assignment
from app.models.availability import Availability
from app.models.employee_role import EmployeeRole
from app.models.time_off_request import TimeOffRequest
from app.models.employee_skill import EmployeeSkill

from app.schemas.employee import EmployeeCreate
from app.schemas.employee import EmployeeResponse

router = APIRouter(
    prefix="/employees",
    tags=["Employees"]
)


@router.get("/", response_model=list[EmployeeResponse])
def get_employees(db: Session = Depends(get_db)):

    return db.query(Employee).all()


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):

    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return employee


@router.post("/", response_model=EmployeeResponse)
def create_employee(employee: EmployeeCreate,
                    db: Session = Depends(get_db)):

    db_employee = Employee(**employee.model_dump())

    db.add(db_employee)

    db.commit()

    db.refresh(db_employee)

    return db_employee


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int,
                     employee: EmployeeCreate,
                     db: Session = Depends(get_db)):

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    for field, value in employee.model_dump().items():
        setattr(db_employee, field, value)

    db.commit()
    db.refresh(db_employee)

    return db_employee


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    """Permanently deletes an employee and every row that references
    them (assignments, availability, employee_roles, time_off_requests,
    employee_skills) -- none of those foreign keys cascade at the DB
    level, so this has to clear them explicitly or the employee delete
    itself would fail with an IntegrityError."""

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.query(Assignment).filter(Assignment.employee_id == employee_id).delete()
    db.query(Availability).filter(Availability.employee_id == employee_id).delete()
    db.query(EmployeeRole).filter(EmployeeRole.employee_id == employee_id).delete()
    db.query(TimeOffRequest).filter(TimeOffRequest.employee_id == employee_id).delete()
    db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == employee_id).delete()

    db.delete(db_employee)
    db.commit()