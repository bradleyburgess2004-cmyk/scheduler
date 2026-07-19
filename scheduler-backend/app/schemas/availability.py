from datetime import date, time
from pydantic import BaseModel


class AvailabilityCreate(BaseModel):

    employee_id: int
    day_of_week: int
    start_time: time
    end_time: time
    availability_date: date | None = None


class AvailabilityResponse(AvailabilityCreate):

    availability_id: int

    class Config:
        from_attributes = True
