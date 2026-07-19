from pydantic import BaseModel


class EmployeeSkillCreate(BaseModel):

    employee_id: int
    skill_id: int


class EmployeeSkillResponse(EmployeeSkillCreate):

    class Config:
        from_attributes = True
