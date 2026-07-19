from datetime import date, time
from pydantic import BaseModel


class ShiftCreate(BaseModel):

    restaurant_id: int
    role_id: int
    shift_date: date
    start_time: time
    end_time: time
    required_employees: int | None = None


class ShiftResponse(ShiftCreate):

    shift_id: int

    class Config:
        from_attributes = True
