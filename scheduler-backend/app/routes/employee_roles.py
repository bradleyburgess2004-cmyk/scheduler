from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.employee_role import EmployeeRole

from app.schemas.employee_role import EmployeeRoleCreate
from app.schemas.employee_role import EmployeeRoleResponse

router = APIRouter(
    prefix="/employee-roles",
    tags=["Employee Roles"]
)


@router.get("/", response_model=list[EmployeeRoleResponse])
def get_employee_roles(db: Session = Depends(get_db)):

    return db.query(EmployeeRole).all()


@router.get("/{employee_id}/{role_id}", response_model=EmployeeRoleResponse)
def get_employee_role(employee_id: int, role_id: int, db: Session = Depends(get_db)):

    record = db.query(EmployeeRole).filter(
        EmployeeRole.employee_id == employee_id,
        EmployeeRole.role_id == role_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Employee role not found")

    return record


@router.post("/", response_model=EmployeeRoleResponse)
def create_employee_role(employee_role: EmployeeRoleCreate,
                          db: Session = Depends(get_db)):

    db_employee_role = EmployeeRole(**employee_role.model_dump())

    db.add(db_employee_role)
    db.commit()
    db.refresh(db_employee_role)

    return db_employee_role


@router.delete("/{employee_id}/{role_id}", status_code=204)
def delete_employee_role(employee_id: int, role_id: int, db: Session = Depends(get_db)):

    record = db.query(EmployeeRole).filter(
        EmployeeRole.employee_id == employee_id,
        EmployeeRole.role_id == role_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Employee role not found")

    db.delete(record)
    db.commit()
