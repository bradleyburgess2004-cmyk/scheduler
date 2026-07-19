from pydantic import BaseModel


class EmployeeRoleCreate(BaseModel):

    employee_id: int
    role_id: int


class EmployeeRoleResponse(EmployeeRoleCreate):

    class Config:
        from_attributes = True
