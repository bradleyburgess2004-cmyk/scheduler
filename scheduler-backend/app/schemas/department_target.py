from decimal import Decimal
from pydantic import BaseModel


class DepartmentTargetCreate(BaseModel):

    restaurant_id: int
    department: str
    daily_hours_required: Decimal | None = None


class DepartmentTargetResponse(DepartmentTargetCreate):

    target_id: int

    class Config:
        from_attributes = True
