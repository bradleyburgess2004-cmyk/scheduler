"""
scheduler.py
=============
Builds and solves the weekly shift-assignment CP-SAT model: which
employee works which shift, minimizing labor cost, subject to:

- two structural rules that always apply regardless of configuration --
  an employee can only be assigned to a shift matching one of their
  roles and within an availability window they've given, and never to
  two shifts that overlap in time -- plus
- whichever ScheduleConstraint rules are ENABLED for this restaurant in
  `restaurant_constraints` (app.optimizer.constraints), each contributing
  either a hard model.Add(...) or a weighted objective penalty term.

Usage:
    python -m app.optimizer.scheduler --restaurant-id 5 --week-start 2026-07-20 [--dry-run]
"""

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from ortools.sat.python import cp_model

from app.database import SessionLocal
from app.models.employee import Employee
from app.models.employee_role import EmployeeRole
from app.models.employee_skill import EmployeeSkill
from app.models.skill import Skill
from app.models.availability import Availability
from app.models.role import Role
from app.models.shift_template import ShiftTemplate
from app.models.shift import Shift
from app.models.assignment import Assignment
from app.models.generated_assignment import GeneratedAssignment
from app.optimizer.constraints import load_constraints_for_restaurant
from app.optimizer.time_utils import day_of_week_from_date, shift_hours

SHORTFALL_PENALTY = 1_000_000


def log(msg):
    print(msg, flush=True)


@dataclass
class EmployeeInfo:
    employee_id: int
    hourly_rate: float
    max_weekly_hours: object  # int | None
    min_weekly_hours: object  # int | None
    role_ids: set


@dataclass
class ShiftInfo:
    shift_id: int
    role_id: int
    shift_date: date
    day_of_week: int
    start_time: time
    end_time: time
    hours: float
    required_employees: int


class SchedulingContext:
    """Bundles the data every ScheduleConstraint.apply() needs: the
    employees/shifts being solved for, the decision variables (only
    populated for eligible (employee, shift) pairs), lookups constraints
    commonly need (role name -> role_id, employee -> skill names), and a
    shared list soft constraints append their objective penalty terms to.
    """

    def __init__(self, restaurant_id, employees, shifts, assignment_vars,
                 role_id_by_name, role_ids_by_department, employee_skill_names):
        self.restaurant_id = restaurant_id
        self.employees = employees
        self.shifts = shifts
        self.x = assignment_vars
        self.role_id_by_name = role_id_by_name
        self.role_ids_by_department = role_ids_by_department
        self.employee_skill_names = employee_skill_names
        self.objective_terms = []
        # (employee_id, shift_id) pairs a LockedAssignmentConstraint wanted
        # to force but couldn't, because no eligible decision variable
        # exists for that pair (unavailable that day, or role mismatch).
        self.skipped_locks = []

        self.shift_ids_by_employee = defaultdict(list)
        self.employee_ids_by_shift = defaultdict(list)
        for (eid, sid) in self.x:
            self.shift_ids_by_employee[eid].append(sid)
            self.employee_ids_by_shift[sid].append(eid)


def _shifts_overlap(s1, s2):
    if s1.shift_date != s2.shift_date:
        return False
    return s1.start_time < s2.end_time and s2.start_time < s1.end_time


def _window_covers_shift(window_start, window_end, shift_start, shift_end):
    return window_start <= shift_start and window_end >= shift_end


def materialize_shifts_for_week(db, restaurant_id, week_start):
    """Get-or-create `shifts` rows for the 7 days starting week_start,
    expanded from this restaurant's recurring shift_templates (the ones
    with day_of_week set). Idempotent -- matched on
    (restaurant_id, role_id, shift_date, start_time, end_time), so
    re-solving the same week reuses the same shift rows rather than
    duplicating them.

    Deliberately excludes any date that's already in the past: once a
    day has occurred, its `assignments` (and `generated_assignments`
    baseline) become the permanent historical record used to derive ML
    training data later, and must never be silently rewritten by a
    later regeneration of the same week. A day still in progress
    (today) or upcoming remains fully regenerable."""
    templates = (
        db.query(ShiftTemplate)
        .filter(
            ShiftTemplate.restaurant_id == restaurant_id,
            ShiftTemplate.day_of_week.isnot(None),
        )
        .all()
    )

    week_dates = [
        week_start + timedelta(days=i) for i in range(7)
        if week_start + timedelta(days=i) >= date.today()
    ]

    existing = {
        (s.role_id, s.shift_date, s.start_time, s.end_time): s
        for s in db.query(Shift).filter(
            Shift.restaurant_id == restaurant_id,
            Shift.shift_date.in_(week_dates),
        ).all()
    }

    created = 0
    week_shift_ids = []
    for template in templates:
        for d in week_dates:
            if day_of_week_from_date(d) != template.day_of_week:
                continue
            key = (template.role_id, d, template.start_time, template.end_time)
            shift = existing.get(key)
            if shift is None:
                shift = Shift(
                    restaurant_id=restaurant_id,
                    role_id=template.role_id,
                    shift_date=d,
                    start_time=template.start_time,
                    end_time=template.end_time,
                    required_employees=template.required_count,
                )
                db.add(shift)
                db.flush()
                existing[key] = shift
                created += 1
            week_shift_ids.append(shift.shift_id)

    log(f"  Shifts materialized for week of {week_start}: {len(week_shift_ids)} total "
        f"({created} newly created)")
    return week_shift_ids


def load_employees(db, restaurant_id):
    roles_by_employee = defaultdict(set)
    for er in (
        db.query(EmployeeRole)
        .join(Employee, Employee.employee_id == EmployeeRole.employee_id)
        .filter(Employee.restaurant_id == restaurant_id)
        .all()
    ):
        roles_by_employee[er.employee_id].add(er.role_id)

    employees = {}
    for emp in db.query(Employee).filter(
        Employee.restaurant_id == restaurant_id, Employee.active.is_(True)
    ).all():
        employees[emp.employee_id] = EmployeeInfo(
            employee_id=emp.employee_id,
            hourly_rate=float(emp.hourly_rate) if emp.hourly_rate is not None else 0.0,
            max_weekly_hours=emp.max_weekly_hours,
            min_weekly_hours=emp.min_weekly_hours,
            role_ids=roles_by_employee.get(emp.employee_id, set()),
        )
    return employees


def load_availability(db, employee_ids, week_dates):
    """Returns dict: employee_id -> list of (day_of_week, start_time, end_time),
    resolved for the specific week being solved (week_dates: that week's 7
    actual calendar dates).

    Availability rows carry an availability_date when they came from a
    dated upload/override (the wide-format/HotSchedules CSV, whose header
    has real dates; or an approved time-off day). The dated-vs-legacy
    check is scoped PER WEEK, not per employee globally: only if this
    employee has at least one dated row actually falling within
    week_dates does this week resolve from dated rows alone (a date in
    the week with no matching row then means unavailable that day).
    Otherwise -- including an employee who has dated rows for some
    *other* week but none for this one -- this week falls back to their
    day-of-week recurring pattern (availability_date IS NULL). Getting
    this scoped per-week, not per-employee, matters: an employee with
    just one isolated dated row (e.g. a single time-off day recorded
    without a full week's dated upload) must not have every other day
    that week silently read as unavailable too."""
    windows = defaultdict(list)
    if not employee_ids:
        return windows

    week_dates_set = set(week_dates)
    rows_by_employee = defaultdict(list)
    for a in db.query(Availability).filter(Availability.employee_id.in_(employee_ids)).all():
        rows_by_employee[a.employee_id].append(a)

    for eid, rows in rows_by_employee.items():
        dated_rows_this_week = [
            a for a in rows if a.availability_date is not None and a.availability_date in week_dates_set
        ]
        if dated_rows_this_week:
            for a in dated_rows_this_week:
                windows[eid].append((a.day_of_week, a.start_time, a.end_time))
        else:
            for a in rows:
                if a.availability_date is None:
                    windows[eid].append((a.day_of_week, a.start_time, a.end_time))
    return windows


def load_employee_skill_names(db, employee_ids):
    names = defaultdict(set)
    if not employee_ids:
        return names
    rows = (
        db.query(EmployeeSkill, Skill.name)
        .join(Skill, Skill.skill_id == EmployeeSkill.skill_id)
        .filter(EmployeeSkill.employee_id.in_(employee_ids))
        .all()
    )
    for es, skill_name in rows:
        names[es.employee_id].add(skill_name)
    return names


def build_shift_infos(db, shift_ids):
    shifts = {}
    for s in db.query(Shift).filter(Shift.shift_id.in_(shift_ids)).all():
        shifts[s.shift_id] = ShiftInfo(
            shift_id=s.shift_id,
            role_id=s.role_id,
            shift_date=s.shift_date,
            day_of_week=day_of_week_from_date(s.shift_date),
            start_time=s.start_time,
            end_time=s.end_time,
            hours=shift_hours(s.start_time, s.end_time),
            required_employees=s.required_employees or 1,
        )
    return shifts


def build_eligible_assignment_vars(model, employees, shifts, availability_by_employee):
    """Only employees whose role matches the shift AND whose availability
    fully covers it get a decision variable -- everyone else is
    structurally ineligible, not merely discouraged."""
    x = {}
    for eid, emp in employees.items():
        windows = availability_by_employee.get(eid, [])
        for sid, shift in shifts.items():
            if shift.role_id not in emp.role_ids:
                continue
            covered = any(
                dow == shift.day_of_week
                and _window_covers_shift(start, end, shift.start_time, shift.end_time)
                for (dow, start, end) in windows
            )
            if not covered:
                continue
            x[(eid, sid)] = model.NewBoolVar(f"x_{eid}_{sid}")
    return x


def add_coverage_constraints(model, shifts, employee_ids_by_shift, x):
    shortfall = {}
    for sid, shift in shifts.items():
        eligible = employee_ids_by_shift.get(sid, [])
        assigned = sum(x[(eid, sid)] for eid in eligible)
        shortfall[sid] = model.NewIntVar(0, shift.required_employees, f"shortfall_{sid}")
        model.Add(assigned + shortfall[sid] == shift.required_employees)
    return shortfall


def add_no_double_booking_constraints(model, shifts, shift_ids_by_employee, x):
    for eid, sids in shift_ids_by_employee.items():
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                s1, s2 = shifts[sids[i]], shifts[sids[j]]
                if _shifts_overlap(s1, s2):
                    model.Add(x[(eid, sids[i])] + x[(eid, sids[j])] <= 1)


def solve_schedule(db, restaurant_id, week_start, time_limit_sec=120):
    log(f"[1/6] Materializing shifts for restaurant_id={restaurant_id}, week of {week_start}...")
    week_shift_ids = materialize_shifts_for_week(db, restaurant_id, week_start)
    db.commit()

    if not week_shift_ids:
        log("  No shift_templates with a day_of_week are configured for this restaurant -- nothing to solve.")
        return None

    log("[2/6] Loading employees, availability, roles, skills...")
    employees = load_employees(db, restaurant_id)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    availability_by_employee = load_availability(db, list(employees.keys()), week_dates)
    employee_skill_names = load_employee_skill_names(db, list(employees.keys()))
    shifts = build_shift_infos(db, week_shift_ids)
    restaurant_roles = db.query(Role).filter(Role.restaurant_id == restaurant_id).all()
    role_id_by_name = {r.role_name: r.role_id for r in restaurant_roles}
    role_ids_by_department = defaultdict(set)
    for r in restaurant_roles:
        if r.department:
            role_ids_by_department[r.department].add(r.role_id)
    log(f"  {len(employees)} active employees, {len(shifts)} shifts to fill")

    log("[3/6] Building eligible assignment variables...")
    model = cp_model.CpModel()
    x = build_eligible_assignment_vars(model, employees, shifts, availability_by_employee)
    log(f"  {len(x)} eligible (employee, shift) pairs")

    context = SchedulingContext(
        restaurant_id, employees, shifts, x, role_id_by_name, role_ids_by_department, employee_skill_names
    )

    log("[4/6] Adding structural constraints (coverage, no double-booking)...")
    shortfall = add_coverage_constraints(model, shifts, context.employee_ids_by_shift, x)
    add_no_double_booking_constraints(model, shifts, context.shift_ids_by_employee, x)

    log("[5/6] Applying configured restaurant constraints...")
    constraints = load_constraints_for_restaurant(db, restaurant_id)
    applied, skipped = 0, []
    for constraint in constraints:
        try:
            constraint.apply(model, context)
            applied += 1
        except NotImplementedError as e:
            skipped.append((type(constraint).__name__, str(e)))
    log(f"  {applied} constraint(s) applied, {len(skipped)} skipped (not yet implemented)")
    for name, reason in skipped:
        log(f"  SKIPPED: {name} -- {reason}")

    log("[6/6] Solving...")
    cost_terms = [
        x[(eid, sid)] * round(employees[eid].hourly_rate * shifts[sid].hours * 100)
        for (eid, sid) in x
    ]
    shortfall_terms = [shortfall[sid] * SHORTFALL_PENALTY for sid in shortfall]
    model.Minimize(sum(cost_terms) + sum(shortfall_terms) + sum(context.objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        log("No feasible solution found.")
        return None

    result_assignments = [(eid, sid) for (eid, sid) in x if solver.Value(x[(eid, sid)])]
    gaps = [(sid, solver.Value(shortfall[sid])) for sid in shortfall if solver.Value(shortfall[sid]) > 0]
    total_cost = sum(employees[eid].hourly_rate * shifts[sid].hours for (eid, sid) in result_assignments)

    log(f"\n{len(result_assignments)} shift assignments made, estimated labor cost ${total_cost:,.2f}")
    if gaps:
        log(f"{len(gaps)} shift slot(s) understaffed:")
        for sid, short in gaps:
            s = shifts[sid]
            log(f"  {s.shift_date} {s.start_time}-{s.end_time} (role_id={s.role_id}): short {short}")
    else:
        log("All shifts fully staffed.")

    if context.skipped_locks:
        log(f"{len(context.skipped_locks)} locked assignment(s) could not be honored (employee unavailable/ineligible):")
        for eid, sid in context.skipped_locks:
            s = shifts[sid]
            log(f"  employee_id={eid} -> {s.shift_date} {s.start_time}-{s.end_time} (role_id={s.role_id})")

    return {
        "assignments": result_assignments,
        "gaps": gaps,
        "skipped_locks": context.skipped_locks,
        "cost": total_cost,
        "shifts": shifts,
        "employees": employees,
    }


def save_assignments(db, result):
    """Writes result['assignments'] into the `assignments` table (the
    live, editable schedule) AND `generated_assignments` (the frozen
    baseline of what the solver actually picked, for later diffing
    against whatever `assignments` says once that shift's date has
    passed). Clears any existing rows for the solved shifts in BOTH
    tables first, so re-solving the same week replaces rather than
    duplicates or accumulates history -- `materialize_shifts_for_week`
    already guarantees result['shifts'] only ever contains shifts whose
    date hasn't passed, so this can never clobber a locked-in past
    day's baseline."""
    if result is None:
        return 0
    shift_ids = list(result["shifts"].keys())
    db.query(Assignment).filter(Assignment.shift_id.in_(shift_ids)).delete(synchronize_session=False)
    db.query(GeneratedAssignment).filter(GeneratedAssignment.shift_id.in_(shift_ids)).delete(synchronize_session=False)
    for eid, sid in result["assignments"]:
        db.add(Assignment(employee_id=eid, shift_id=sid))
        db.add(GeneratedAssignment(employee_id=eid, shift_id=sid))
    db.commit()
    return len(result["assignments"])


def main():
    parser = argparse.ArgumentParser(description="Solve a week's schedule for a restaurant")
    parser.add_argument("--restaurant-id", type=int, required=True)
    parser.add_argument("--week-start", required=True, help="YYYY-MM-DD, the first day of the week to solve")
    parser.add_argument("--time-limit", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true", help="Solve and report, but don't save assignments")
    args = parser.parse_args()

    week_start = datetime.strptime(args.week_start, "%Y-%m-%d").date()

    db = SessionLocal()
    try:
        result = solve_schedule(db, args.restaurant_id, week_start, args.time_limit)
        if result is not None:
            if args.dry_run:
                log("\n[DRY RUN] Assignments not saved.")
            else:
                saved = save_assignments(db, result)
                log(f"\nSaved {saved} assignments to the database.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
