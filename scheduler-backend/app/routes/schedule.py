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
from app.optimizer.scheduler import solve_schedule
from app.optimizer.scheduler import save_assignments

from app.schemas.schedule import ScheduleResponse
from app.schemas.schedule import EmployeeScheduleRow
from app.schemas.schedule import EmployeeDay
from app.schemas.schedule import ScheduledShift
from app.schemas.schedule import DailyTotal
from app.schemas.schedule import GenerateScheduleResponse

router = APIRouter(
    prefix="/restaurants",
    tags=["Schedule"]
)


@router.get("/{restaurant_id}/schedule", response_model=ScheduleResponse)
def get_schedule(
    restaurant_id: int,
    week_start: date_type = Query(..., description="First day of the week, YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Returns one week's schedule shaped for a calendar grid: one row per
    active employee, one cell per day, plus hour/cost totals per employee
    and per day. Reads whatever is currently in `shifts`/`assignments` for
    this restaurant and week -- run the solver first if nothing's there."""

    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    week_dates = [week_start + timedelta(days=i) for i in range(7)]

    shift_rows = (
        db.query(Shift, Role.role_name)
        .join(Role, Role.role_id == Shift.role_id)
        .filter(Shift.restaurant_id == restaurant_id, Shift.shift_date.in_(week_dates))
        .all()
    )
    shift_by_id = {s.shift_id: (s, role_name) for s, role_name in shift_rows}

    assignments = (
        db.query(Assignment).filter(Assignment.shift_id.in_(shift_by_id.keys())).all()
        if shift_by_id else []
    )

    assignments_by_shift = defaultdict(list)
    assignments_by_employee = defaultdict(list)
    for a in assignments:
        assignments_by_shift[a.shift_id].append(a)
        assignments_by_employee[a.employee_id].append(a)

    employees = (
        db.query(Employee)
        .filter(Employee.restaurant_id == restaurant_id, Employee.active.is_(True))
        .all()
    )
    employees_by_id = {e.employee_id: e for e in employees}
    roles_by_id = {
        r.role_id: r for r in db.query(Role).filter(Role.restaurant_id == restaurant_id).all()
    }

    employee_rows = []
    for emp in employees:
        hourly_rate = float(emp.hourly_rate) if emp.hourly_rate is not None else 0.0
        total_hours = 0.0
        days = []
        for d in week_dates:
            day_shifts = []
            for a in assignments_by_employee.get(emp.employee_id, []):
                shift, role_name = shift_by_id[a.shift_id]
                if shift.shift_date != d:
                    continue
                hours = shift_hours(shift.start_time, shift.end_time)
                total_hours += hours
                assigned_count = len(assignments_by_shift.get(shift.shift_id, []))
                day_shifts.append(ScheduledShift(
                    assignment_id=a.assignment_id,
                    shift_id=shift.shift_id,
                    role_id=shift.role_id,
                    role_name=role_name,
                    start_time=shift.start_time,
                    end_time=shift.end_time,
                    hours=round(hours, 2),
                    required_employees=shift.required_employees or 1,
                    understaffed=assigned_count < (shift.required_employees or 1),
                ))
            days.append(EmployeeDay(date=d, shifts=day_shifts))
        role = roles_by_id.get(emp.role_id)
        employee_rows.append(EmployeeScheduleRow(
            employee_id=emp.employee_id,
            first_name=emp.first_name,
            last_name=emp.last_name,
            role_id=emp.role_id,
            role_name=role.role_name if role else None,
            department=role.department if role else None,
            hourly_rate=hourly_rate,
            total_hours=round(total_hours, 2),
            total_cost=round(total_hours * hourly_rate, 2),
            days=days,
        ))

    daily_totals = []
    week_total_cost = 0.0
    week_understaffed = 0
    for d in week_dates:
        day_shift_ids = [sid for sid, (s, _) in shift_by_id.items() if s.shift_date == d]
        headcount = 0
        day_cost = 0.0
        day_understaffed = 0
        for sid in day_shift_ids:
            shift, _ = shift_by_id[sid]
            hours = shift_hours(shift.start_time, shift.end_time)
            shift_assignments = assignments_by_shift.get(sid, [])
            headcount += len(shift_assignments)
            for a in shift_assignments:
                emp = employees_by_id.get(a.employee_id)
                rate = float(emp.hourly_rate) if emp and emp.hourly_rate is not None else 0.0
                day_cost += hours * rate
            if len(shift_assignments) < (shift.required_employees or 1):
                day_understaffed += 1
        week_total_cost += day_cost
        week_understaffed += day_understaffed
        daily_totals.append(DailyTotal(
            date=d,
            headcount=headcount,
            cost=round(day_cost, 2),
            understaffed_shifts=day_understaffed,
        ))

    return ScheduleResponse(
        restaurant_id=restaurant_id,
        week_start=week_start,
        week_dates=week_dates,
        employees=employee_rows,
        daily_totals=daily_totals,
        week_total_cost=round(week_total_cost, 2),
        week_total_assignments=len(assignments),
        week_understaffed_shifts=week_understaffed,
    )


@router.post("/{restaurant_id}/schedule/generate", response_model=GenerateScheduleResponse)
def generate_schedule(
    restaurant_id: int,
    week_start: date_type = Query(..., description="First day of the week, YYYY-MM-DD"),
    time_limit: int = Query(120, ge=10, le=300, description="Max solver time in seconds"),
    template_id: int | None = Query(None, description="Optional ScheduleTemplate to softly bias assignments toward"),
    template_weight: float | None = Query(
        None, ge=0, le=1000,
        description="Dollar-equivalent reward per honored template shift; higher = stronger adherence",
    ),
    db: Session = Depends(get_db),
):
    """Runs the CP-SAT solver for this restaurant/week and saves the
    result, replacing any existing assignments for that week -- the
    same thing `python -m app.optimizer.scheduler` does from the CLI,
    exposed so the frontend doesn't need shell access to generate a
    schedule. If template_id is given, the solver is softly biased
    toward reproducing that saved schedule's pattern, without ever
    overriding availability/time-off/coverage/other enabled constraints."""

    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    result = solve_schedule(db, restaurant_id, week_start, time_limit, template_id, template_weight)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="No feasible schedule could be generated for this week with the current "
                   "constraints and availability. Try relaxing a constraint or check that shift "
                   "templates are configured.",
        )

    saved = save_assignments(db, result)
    return GenerateScheduleResponse(
        restaurant_id=restaurant_id,
        week_start=week_start,
        assignments_saved=saved,
        total_cost=round(result["cost"], 2),
        understaffed_shifts=len(result["gaps"]),
        locked_assignments_skipped=len(result["skipped_locks"]),
        template_id_used=result["template_id"],
        template_entries_applied=result["template_entries_applied"],
        template_entries_unmatched=result["template_entries_unmatched"],
    )
