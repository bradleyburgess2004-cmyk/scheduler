from datetime import date, time
from pydantic import BaseModel


class ScheduledShift(BaseModel):

    assignment_id: int
    shift_id: int
    role_id: int
    role_name: str
    start_time: time
    end_time: time
    hours: float
    required_employees: int
    understaffed: bool


class EmployeeDay(BaseModel):

    date: date
    shifts: list[ScheduledShift]


class EmployeeScheduleRow(BaseModel):

    employee_id: int
    first_name: str
    last_name: str
    role_id: int | None
    role_name: str | None
    department: str | None
    hourly_rate: float
    total_hours: float
    total_cost: float
    days: list[EmployeeDay]


class DailyTotal(BaseModel):

    date: date
    headcount: int
    cost: float
    understaffed_shifts: int


class ScheduleResponse(BaseModel):

    restaurant_id: int
    week_start: date
    week_dates: list[date]
    employees: list[EmployeeScheduleRow]
    daily_totals: list[DailyTotal]
    week_total_cost: float
    week_total_assignments: int
    week_understaffed_shifts: int


class GenerateScheduleResponse(BaseModel):

    restaurant_id: int
    week_start: date
    assignments_saved: int
    total_cost: float
    understaffed_shifts: int
    locked_assignments_skipped: int
