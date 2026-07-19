from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant
from app.models.employee import Employee
from app.models.role import Role
from app.models.shift import Shift
from app.models.assignment import Assignment

from app.optimizer.time_utils import shift_hours

from app.schemas.labor_analytics import LaborAnalyticsResponse
from app.schemas.labor_analytics import WeeklyLaborSummary
from app.schemas.labor_analytics import DepartmentCostBreakdown

router = APIRouter(
    prefix="/restaurants",
    tags=["Labor Analytics"]
)


def _week_start(d):
    return d - timedelta(days=d.weekday())


@router.get("/{restaurant_id}/labor-analytics", response_model=LaborAnalyticsResponse)
def get_labor_analytics(
    restaurant_id: int,
    weeks: int = Query(8, ge=1, le=52, description="Number of most recent weeks to include in the trend"),
    week_start: date_type | None = Query(
        None, description="Monday of the week the department breakdown should cover; defaults to the most recent week with any shift data"
    ),
    db: Session = Depends(get_db),
):
    """Aggregates whatever shifts/assignments already exist for this
    restaurant into a per-week cost trend plus a department cost
    breakdown for the most recent week. Reads straight from the DB --
    no solver call, no caching -- since at real-world scale (a
    restaurant's weekly shift volume) this is a handful of queries over
    at most a few thousand rows."""

    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    shift_rows = db.query(Shift).filter(Shift.restaurant_id == restaurant_id).all()
    if not shift_rows:
        return LaborAnalyticsResponse(
            restaurant_id=restaurant_id,
            weekly_trend=[],
            breakdown_week_start=week_start,
            department_breakdown=[],
        )

    shift_by_id = {s.shift_id: s for s in shift_rows}
    roles_by_id = {r.role_id: r for r in db.query(Role).filter(Role.restaurant_id == restaurant_id).all()}
    employees_by_id = {e.employee_id: e for e in db.query(Employee).filter(Employee.restaurant_id == restaurant_id).all()}

    assignments = db.query(Assignment).filter(Assignment.shift_id.in_(shift_by_id.keys())).all()
    assignments_by_shift = defaultdict(list)
    for a in assignments:
        assignments_by_shift[a.shift_id].append(a)

    # bucket shifts by the Monday of their week
    shifts_by_week = defaultdict(list)
    for s in shift_rows:
        shifts_by_week[_week_start(s.shift_date)].append(s)

    def hourly_rate(employee_id):
        emp = employees_by_id.get(employee_id)
        return float(emp.hourly_rate) if emp and emp.hourly_rate is not None else 0.0

    weekly_summaries = []
    for wk, shifts in shifts_by_week.items():
        total_cost = 0.0
        total_assignments = 0
        understaffed_shifts = 0
        total_shifts = len(shifts)
        for s in shifts:
            hours = shift_hours(s.start_time, s.end_time)
            shift_assignments = assignments_by_shift.get(s.shift_id, [])
            total_assignments += len(shift_assignments)
            for a in shift_assignments:
                total_cost += hours * hourly_rate(a.employee_id)
            if len(shift_assignments) < (s.required_employees or 1):
                understaffed_shifts += 1
        weekly_summaries.append(WeeklyLaborSummary(
            week_start=wk,
            total_cost=round(total_cost, 2),
            total_assignments=total_assignments,
            understaffed_shifts=understaffed_shifts,
            total_shifts=total_shifts,
        ))

    weekly_summaries.sort(key=lambda w: w.week_start)
    trend = weekly_summaries[-weeks:]

    breakdown_week_start = week_start if week_start is not None else weekly_summaries[-1].week_start
    breakdown_shifts = shifts_by_week.get(breakdown_week_start, [])

    department_totals = defaultdict(lambda: {"cost": 0.0, "hours": 0.0, "assignments": 0})
    for s in breakdown_shifts:
        role = roles_by_id.get(s.role_id)
        department = role.department if role and role.department else "Other"
        hours = shift_hours(s.start_time, s.end_time)
        for a in assignments_by_shift.get(s.shift_id, []):
            department_totals[department]["cost"] += hours * hourly_rate(a.employee_id)
            department_totals[department]["hours"] += hours
            department_totals[department]["assignments"] += 1

    department_breakdown = [
        DepartmentCostBreakdown(
            department=dept,
            cost=round(totals["cost"], 2),
            hours=round(totals["hours"], 2),
            assignments=totals["assignments"],
        )
        for dept, totals in sorted(department_totals.items(), key=lambda kv: kv[1]["cost"], reverse=True)
    ]

    return LaborAnalyticsResponse(
        restaurant_id=restaurant_id,
        weekly_trend=trend,
        breakdown_week_start=breakdown_week_start,
        department_breakdown=department_breakdown,
    )
