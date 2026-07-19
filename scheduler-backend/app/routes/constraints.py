from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.constraint import Constraint

from app.optimizer.constraints.param_specs import CONSTRAINT_PARAM_SPECS

from app.schemas.constraint import ConstraintCreate
from app.schemas.constraint import ConstraintResponse

router = APIRouter(
    prefix="/constraints",
    tags=["Constraints"]
)


def _to_response(constraint: Constraint) -> ConstraintResponse:
    response = ConstraintResponse.model_validate(constraint)
    if constraint.class_name in CONSTRAINT_PARAM_SPECS:
        response.parameter_spec = CONSTRAINT_PARAM_SPECS[constraint.class_name]
    return response


@router.get("/", response_model=list[ConstraintResponse])
def get_constraints(db: Session = Depends(get_db)):

    return [_to_response(c) for c in db.query(Constraint).all()]


@router.get("/{constraint_id}", response_model=ConstraintResponse)
def get_constraint(constraint_id: int, db: Session = Depends(get_db)):

    constraint = db.query(Constraint).filter(Constraint.constraint_id == constraint_id).first()

    if not constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")

    return _to_response(constraint)


@router.post("/", response_model=ConstraintResponse)
def create_constraint(constraint: ConstraintCreate,
                       db: Session = Depends(get_db)):

    db_constraint = Constraint(**constraint.model_dump())

    db.add(db_constraint)
    db.commit()
    db.refresh(db_constraint)

    return db_constraint


@router.put("/{constraint_id}", response_model=ConstraintResponse)
def update_constraint(constraint_id: int,
                       constraint: ConstraintCreate,
                       db: Session = Depends(get_db)):

    db_constraint = db.query(Constraint).filter(Constraint.constraint_id == constraint_id).first()

    if not db_constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")

    for field, value in constraint.model_dump().items():
        setattr(db_constraint, field, value)

    db.commit()
    db.refresh(db_constraint)

    return db_constraint


@router.delete("/{constraint_id}", status_code=204)
def delete_constraint(constraint_id: int, db: Session = Depends(get_db)):

    db_constraint = db.query(Constraint).filter(Constraint.constraint_id == constraint_id).first()

    if not db_constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")

    db.delete(db_constraint)
    db.commit()
