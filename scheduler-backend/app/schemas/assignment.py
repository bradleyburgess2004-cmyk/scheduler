from pydantic import BaseModel


class AssignmentCreate(BaseModel):

    shift_id: int
    employee_id: int


class AssignmentResponse(AssignmentCreate):

    assignment_id: int

    class Config:
        from_attributes = True
