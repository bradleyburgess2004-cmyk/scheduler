from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class EmployeeCreate(BaseModel):
    restaurant_id: int

    first_name: str
    last_name: str

    role_id: int | None = None

    active: bool = True

    hourly_rate: Decimal | None = None

    hire_date: date | None = None

    max_weekly_hours: int | None = None

    overtime_limit: int | None = None

    external_employee_id: str | None = None

    min_weekly_hours: int | None = None


class EmployeeResponse(BaseModel):

    employee_id: int

    restaurant_id: int

    first_name: str
    last_name: str

    role_id: int | None

    hourly_rate: Decimal | None

    hire_date: date | None

    active: bool

    max_weekly_hours: int | None

    overtime_limit: int | None

    external_employee_id: str | None

    min_weekly_hours: int | None


    class Config:
        from_attributes = True