from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.role import Role

from app.schemas.role import RoleCreate
from app.schemas.role import RoleResponse

router = APIRouter(
    prefix="/roles",
    tags=["Roles"]
)


@router.get("/", response_model=list[RoleResponse])
def get_roles(db: Session = Depends(get_db)):

    return db.query(Role).all()


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(role_id: int, db: Session = Depends(get_db)):

    role = db.query(Role).filter(Role.role_id == role_id).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return role


@router.post("/", response_model=RoleResponse)
def create_role(role: RoleCreate, db: Session = Depends(get_db)):

    db_role = Role(**role.model_dump())

    db.add(db_role)
    db.commit()
    db.refresh(db_role)

    return db_role


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(role_id: int, role: RoleCreate, db: Session = Depends(get_db)):

    db_role = db.query(Role).filter(Role.role_id == role_id).first()

    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")

    for field, value in role.model_dump().items():
        setattr(db_role, field, value)

    db.commit()
    db.refresh(db_role)

    return db_role


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, db: Session = Depends(get_db)):

    db_role = db.query(Role).filter(Role.role_id == role_id).first()

    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")

    db.delete(db_role)
    db.commit()
