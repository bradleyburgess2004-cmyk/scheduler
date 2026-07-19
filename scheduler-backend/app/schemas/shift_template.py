from datetime import time
from pydantic import BaseModel


class ShiftTemplateCreate(BaseModel):

    restaurant_id: int
    role_id: int
    start_time: time
    end_time: time
    day_of_week: int | None = None
    required_count: int | None = None


class ShiftTemplateResponse(ShiftTemplateCreate):

    template_id: int

    class Config:
        from_attributes = True
