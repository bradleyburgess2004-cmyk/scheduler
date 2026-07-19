from pydantic import BaseModel


class RoleCreate(BaseModel):

    restaurant_id: int
    role_name: str
    department: str | None = None


class RoleResponse(RoleCreate):

    role_id: int

    class Config:
        from_attributes = True
