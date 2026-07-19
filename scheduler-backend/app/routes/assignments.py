from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.assignment import Assignment

from app.schemas.assignment import AssignmentCreate
from app.schemas.assignment import AssignmentResponse

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)


@router.get("/", response_model=list[AssignmentResponse])
def get_assignments(db: Session = Depends(get_db)):

    return db.query(Assignment).all()


@router.get("/{assignment_id}", response_model=AssignmentResponse)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):

    assignment = db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return assignment


@router.post("/", response_model=AssignmentResponse)
def create_assignment(assignment: AssignmentCreate,
                       db: Session = Depends(get_db)):

    db_assignment = Assignment(**assignment.model_dump())

    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)

    return db_assignment


@router.put("/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(assignment_id: int,
                       assignment: AssignmentCreate,
                       db: Session = Depends(get_db)):

    db_assignment = db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()

    if not db_assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    for field, value in assignment.model_dump().items():
        setattr(db_assignment, field, value)

    db.commit()
    db.refresh(db_assignment)

    return db_assignment


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):

    db_assignment = db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()

    if not db_assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    db.delete(db_assignment)
    db.commit()
