from datetime import date
from pydantic import BaseModel


class TimeOffRequestCreate(BaseModel):

    employee_id: int
    start_date: date
    end_date: date
    approved: bool | None = None


class TimeOffRequestResponse(TimeOffRequestCreate):

    request_id: int

    class Config:
        from_attributes = True
