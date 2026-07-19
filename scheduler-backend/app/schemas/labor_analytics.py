from datetime import date
from pydantic import BaseModel


class WeeklyLaborSummary(BaseModel):

    week_start: date
    total_cost: float
    total_assignments: int
    understaffed_shifts: int
    total_shifts: int


class DepartmentCostBreakdown(BaseModel):

    department: str
    cost: float
    hours: float
    assignments: int


class LaborAnalyticsResponse(BaseModel):

    restaurant_id: int
    weekly_trend: list[WeeklyLaborSummary]
    breakdown_week_start: date | None
    department_breakdown: list[DepartmentCostBreakdown]
