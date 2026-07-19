"""
import_weekly_workflow.py
===========================
Imports weekly_workflow/state CSVs (employees.csv, availability.csv,
shift_requirements.csv, targets.csv) into scheduler_db under a single
restaurant.

Safe to re-run: everything is matched on a natural key so re-importing
updates existing rows instead of duplicating them --
    restaurant          matched by name
    roles               matched by (restaurant_id, role_name)
    employees           matched by external_employee_id (the CSV's employee_id slug)
    employee_roles      fully resynced per employee (added/removed to match the CSV)
    availability        fully replaced per employee (this file is a weekly snapshot)
    shift_templates     matched by (restaurant_id, role_id, day_of_week, start_time, end_time)
    department_targets  matched by (restaurant_id, department)

The whole run is one transaction -- either everything commits, or (with
--dry-run) everything is parsed and reported but rolled back at the end.

Usage:
    python -m app.scripts.import_weekly_workflow \\
        --state-dir ../weekly_workflow/state \\
        --restaurant-name "The Dwarf House" \\
        [--dry-run]
"""

import argparse
import csv
import io
import os
import re
from collections import defaultdict
from datetime import datetime

HEADER_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")


def parse_header_date(cell):
    """Pulls the real calendar date out of a wide-format header cell like
    'Sun  7/19/26' -> date(2026, 7, 19). Returns None if the cell has no
    recognizable date (e.g. a header that's just 'Sun' with no date, or
    the leading 'Employees' cell)."""
    m = HEADER_DATE_RE.search(cell)
    if not m:
        return None
    month, day, year = (int(g) for g in m.groups())
    if year < 100:
        year += 2000
    return datetime(year, month, day).date()

from app.database import SessionLocal
from app.models.restaurant import Restaurant
from app.models.role import Role
from app.models.employee import Employee
from app.models.employee_role import EmployeeRole
from app.models.availability import Availability
from app.models.shift_template import ShiftTemplate
from app.models.department_target import DepartmentTarget

DAY_TO_INT = {"Sun": 0, "Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6}


def log(msg):
    print(msg, flush=True)


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_time(s):
    return datetime.strptime(s.strip(), "%H:%M").time()


def parse_time_12hr(s):
    """'11:00 AM' / '5:00 PM' -> 24-hour 'HH:MM' string."""
    return datetime.strptime(s.strip(), "%I:%M %p").strftime("%H:%M")


def normalize_day(s):
    day = s.strip()[:3].capitalize()
    if day not in DAY_TO_INT:
        raise ValueError(f"Unrecognized day '{s}'")
    return day


def parse_availability_cell(cell):
    """A HotSchedules-style wide-export cell -> list of (start, end)
    24-hour 'HH:MM' windows. 'Available All Day' -> the full day,
    'Unavailable...' -> no windows, 'Partially Available H:MM AM/PM -
    H:MM AM/PM[, H:MM AM/PM - H:MM AM/PM...]' -> the given window(s)."""
    cell = cell.strip()
    low = cell.lower()
    if not cell or low.startswith("unavailable"):
        return []
    if low.startswith("available all day"):
        return [("00:00", "23:59")]
    if low.startswith("partially available"):
        body = cell[len("Partially Available"):].strip()
        windows = []
        for part in body.split(","):
            part = part.strip()
            m = re.match(r"(\d{1,2}:\d{2}\s*[APap][Mm])\s*-\s*(\d{1,2}:\d{2}\s*[APap][Mm])", part)
            if not m:
                continue
            start, end = parse_time_12hr(m.group(1)), parse_time_12hr(m.group(2))
            if end == "00:00":
                end = "23:59"
            windows.append((start, end))
        return windows
    return []


def is_wide_availability_format(fieldnames):
    """True for the raw HotSchedules export (Employees, Sun 7/19/26,
    Mon 7/20/26, ...); False for our own long format (employee_id, day,
    start_time, end_time)."""
    normalized = {(h or "").strip().lower() for h in fieldnames}
    return not {"employee_id", "day", "start_time", "end_time"}.issubset(normalized)


def get_or_create_restaurant(db, name):
    restaurant = db.query(Restaurant).filter(Restaurant.name == name).first()
    if restaurant:
        return restaurant, False
    restaurant = Restaurant(name=name)
    db.add(restaurant)
    db.flush()
    return restaurant, True


def get_or_create_roles(db, restaurant, role_names):
    existing = {
        r.role_name: r
        for r in db.query(Role).filter(Role.restaurant_id == restaurant.restaurant_id).all()
    }
    created = 0
    for name in sorted(role_names):
        if name not in existing:
            role = Role(restaurant_id=restaurant.restaurant_id, role_name=name)
            db.add(role)
            db.flush()
            existing[name] = role
            created += 1
    return existing, created


def import_employees(db, restaurant, roles_by_name, employees_path):
    rows = read_csv(employees_path)

    seen_ids = {}
    duplicate_ids = []
    for row in rows:
        eid = row["employee_id"].strip()
        if eid in seen_ids:
            duplicate_ids.append(eid)
        seen_ids[eid] = row  # last occurrence in the file wins

    existing = {
        e.external_employee_id: e
        for e in db.query(Employee).filter(Employee.restaurant_id == restaurant.restaurant_id).all()
        if e.external_employee_id
    }

    inserted, updated, no_role = 0, 0, []

    for eid, row in seen_ids.items():
        name = row["name"].strip()
        parts = name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        role_names = [r.strip() for r in row["roles"].split(";") if r.strip()]
        if not role_names:
            no_role.append(eid)
        primary_role = roles_by_name.get(role_names[0]) if role_names else None

        hourly_rate = float(row["hourly_rate"]) if row["hourly_rate"].strip() else None
        min_hours = int(float(row["min_hours"])) if row["min_hours"].strip() else None
        max_hours = int(float(row["max_hours"])) if row["max_hours"].strip() else None

        emp = existing.get(eid)
        if emp is None:
            emp = Employee(restaurant_id=restaurant.restaurant_id, external_employee_id=eid)
            db.add(emp)
            inserted += 1
        else:
            updated += 1

        emp.first_name = first_name
        emp.last_name = last_name
        emp.role_id = primary_role.role_id if primary_role else None
        emp.hourly_rate = hourly_rate
        emp.min_weekly_hours = min_hours
        emp.max_weekly_hours = max_hours
        if emp.active is None:
            emp.active = True

        db.flush()  # assign employee_id for new rows

        wanted_role_ids = {roles_by_name[r].role_id for r in role_names if r in roles_by_name}
        current = db.query(EmployeeRole).filter(EmployeeRole.employee_id == emp.employee_id).all()
        current_role_ids = {er.role_id for er in current}

        for er in current:
            if er.role_id not in wanted_role_ids:
                db.delete(er)
        for rid in wanted_role_ids - current_role_ids:
            db.add(EmployeeRole(employee_id=emp.employee_id, role_id=rid))
        db.flush()

        existing[eid] = emp

    log(f"  Employees: {inserted} inserted, {updated} updated "
        f"({len(rows)} rows read, {len(seen_ids)} unique ids)")
    if duplicate_ids:
        log(f"  WARNING: duplicate employee_id in employees.csv (last row wins): "
            f"{sorted(set(duplicate_ids))}")
    if no_role:
        log(f"  WARNING: {len(no_role)} employee(s) with no role listed: {no_role}")

    return existing


def _apply_availability_entries(db, entries, touched_employee_ids, replace_dates=None):
    """entries: list of (employee_id, day_of_week, start_time, end_time,
    availability_date) already-resolved tuples (internal employee_id,
    real time/date objects; availability_date is None for the undated
    long format). touched_employee_ids: every employee matched by this
    upload, INCLUDING ones with zero entries (e.g. someone who reported
    unavailable every single day) -- their existing availability for
    the replaced range still needs to be cleared, not left stale, or a
    "replace" upload would silently keep old data for exactly the
    people whose availability changed the most.

    replace_dates: the set of specific calendar dates this upload
    covers (from the wide-format header's real dates). When given, only
    each touched employee's rows on THOSE dates are cleared before
    inserting the new ones -- other weeks' previously-uploaded
    availability is left alone. When None (the undated long format,
    which carries no date info to scope by), falls back to the old
    behavior of replacing the employee's entire availability history.

    Shared by both the long-format and wide-format (raw HotSchedules
    export) importers so the actual DB-write logic lives in exactly one
    place."""
    by_employee = defaultdict(list)
    for employee_id, day_of_week, start_time, end_time, availability_date in entries:
        by_employee[employee_id].append((day_of_week, start_time, end_time, availability_date))

    inserted = 0
    for employee_id in touched_employee_ids:
        query = db.query(Availability).filter(Availability.employee_id == employee_id)
        if replace_dates is not None:
            query = query.filter(Availability.availability_date.in_(replace_dates))
        query.delete(synchronize_session=False)
        for day_of_week, start_time, end_time, availability_date in by_employee.get(employee_id, []):
            db.add(Availability(
                employee_id=employee_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                availability_date=availability_date,
            ))
            inserted += 1
    db.flush()
    return len(touched_employee_ids), inserted


def import_availability(db, employees_by_ext_id, rows):
    """rows: parsed long-format CSV rows (employee_id, day, start_time,
    end_time), where employee_id is the external_employee_id slug --
    caller reads them from wherever (a file path for the CLI, an
    uploaded file's contents for the API).

    Returns a stats dict so callers (e.g. an API response) can report
    what happened without re-deriving it from log output."""
    entries = []
    touched_employee_ids = set()
    orphans = set()
    for row in rows:
        eid = row["employee_id"].strip()
        emp = employees_by_ext_id.get(eid)
        if emp is None:
            orphans.add(eid)
            continue
        touched_employee_ids.add(emp.employee_id)
        entries.append((
            emp.employee_id,
            DAY_TO_INT[normalize_day(row["day"])],
            parse_time(row["start_time"]),
            parse_time(row["end_time"]),
            None,
        ))

    # No date info in this format -- keeps the old full-history-replace
    # behavior (replace_dates=None) rather than the wide format's
    # date-scoped overwrite.
    employees_updated, windows_applied = _apply_availability_entries(db, entries, touched_employee_ids)

    log(f"  Availability: {windows_applied} windows applied for {employees_updated} employees "
        f"({len(rows)} rows read)")
    if orphans:
        log(f"  WARNING: availability.csv has {len(orphans)} employee_id(s) not found in "
            f"employees.csv: {sorted(orphans)}")

    return {
        "rows_read": len(rows),
        "employees_updated": employees_updated,
        "windows_applied": windows_applied,
        "orphaned_employee_ids": sorted(orphans),
        "unmatched_names": [],
        "created_employees": [],
    }


def import_availability_wide(db, employees_by_name, csv_text, restaurant_id=None, auto_create_employees=False):
    """csv_text: the raw HotSchedules-style export -- first column is
    the employee's full name, remaining columns are one per day (header
    cell starting with the 3-letter day abbreviation, e.g. 'Sun
    7/19/26'). employees_by_name: dict of lowercased 'first last' ->
    Employee, for the restaurant being imported into. No pre-formatting
    of this file is needed -- it's parsed exactly as HotSchedules
    exports it.

    If auto_create_employees is True (requires restaurant_id), a name
    in the file that doesn't match any existing employee gets a new
    Employee row created on the spot (first/last name split the same
    way import_employees() does), and that row is treated as matched
    for the rest of this import -- its availability from this file gets
    applied like everyone else's, not left empty. New rows get no role,
    hourly_rate, etc. -- just enough to exist and receive availability;
    someone still needs to fill in the rest on the Employees page.
    """
    if auto_create_employees and restaurant_id is None:
        raise ValueError("restaurant_id is required when auto_create_employees is True")

    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    day_cols = [h.strip()[:3] for h in header[1:]]
    date_cols = [parse_header_date(h) for h in header[1:]]
    replace_dates = {d for d in date_cols if d is not None}

    entries = []
    touched_employee_ids = set()
    unmatched_names = set()
    created_names = []
    rows_read = 0
    for row in reader:
        if not row or not row[0].strip():
            continue
        rows_read += 1
        name = row[0].strip()
        emp = employees_by_name.get(name.lower())
        if emp is None:
            if not auto_create_employees:
                unmatched_names.add(name)
                continue
            parts = name.split(" ", 1)
            emp = Employee(
                restaurant_id=restaurant_id,
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
                active=True,
            )
            db.add(emp)
            db.flush()  # assign employee_id
            employees_by_name[name.lower()] = emp
            created_names.append(name)
        touched_employee_ids.add(emp.employee_id)
        for day, date_val, cell in zip(day_cols, date_cols, row[1:]):
            for (start_str, end_str) in parse_availability_cell(cell):
                entries.append((
                    emp.employee_id,
                    DAY_TO_INT[normalize_day(day)],
                    parse_time(start_str),
                    parse_time(end_str),
                    date_val,
                ))

    # replace_dates scopes the delete-then-reinsert to just the dates this
    # file actually covers (parsed from the header, e.g. 7/19/26-7/25/26)
    # -- a later week's upload no longer wipes out an earlier week's
    # already-uploaded availability, and vice versa. Falls back to the
    # old full-history replace only if the header had no parseable dates
    # at all (an unusual, non-HotSchedules wide file).
    employees_updated, windows_applied = _apply_availability_entries(
        db, entries, touched_employee_ids, replace_dates=replace_dates or None
    )

    log(f"  Availability (wide format): {windows_applied} windows applied for "
        f"{employees_updated} employees ({rows_read} employee rows read)")
    if created_names:
        log(f"  Auto-created {len(created_names)} new employee(s) from unmatched names: {sorted(created_names)}")
    if unmatched_names:
        log(f"  WARNING: {len(unmatched_names)} name(s) in the file didn't match any employee: "
            f"{sorted(unmatched_names)}")

    return {
        "rows_read": rows_read,
        "employees_updated": employees_updated,
        "windows_applied": windows_applied,
        "orphaned_employee_ids": [],
        "unmatched_names": sorted(unmatched_names),
        "created_employees": sorted(created_names),
    }


def import_shift_requirements(db, restaurant, roles_by_name, shift_requirements_path):
    rows = read_csv(shift_requirements_path)

    existing = {
        (st.role_id, st.day_of_week, st.start_time, st.end_time): st
        for st in db.query(ShiftTemplate).filter(
            ShiftTemplate.restaurant_id == restaurant.restaurant_id,
            ShiftTemplate.day_of_week.isnot(None),
        ).all()
    }

    inserted, updated, unmatched_roles = 0, 0, set()

    for row in rows:
        role_name = row["role"].strip()
        role = roles_by_name.get(role_name)
        if role is None:
            unmatched_roles.add(role_name)
            continue

        day_of_week = DAY_TO_INT[normalize_day(row["day"])]
        start_time = parse_time(row["start_time"])
        end_time = parse_time(row["end_time"])
        count_needed = int(row["count_needed"])

        key = (role.role_id, day_of_week, start_time, end_time)
        template = existing.get(key)
        if template is None:
            template = ShiftTemplate(
                restaurant_id=restaurant.restaurant_id,
                role_id=role.role_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
            )
            db.add(template)
            existing[key] = template
            inserted += 1
        else:
            updated += 1
        template.required_count = count_needed
    db.flush()

    log(f"  Shift requirements: {inserted} inserted, {updated} updated ({len(rows)} rows read)")
    if unmatched_roles:
        log(f"  WARNING: shift_requirements.csv references role(s) not in the role vocabulary: "
            f"{sorted(unmatched_roles)}")


def import_targets(db, restaurant, targets_path):
    rows = read_csv(targets_path)

    existing = {
        dt.department: dt
        for dt in db.query(DepartmentTarget).filter(
            DepartmentTarget.restaurant_id == restaurant.restaurant_id
        ).all()
    }

    inserted, updated = 0, 0
    for row in rows:
        dept = row["Department"].strip()
        hours = float(row["Daily Hours Required"])
        target = existing.get(dept)
        if target is None:
            target = DepartmentTarget(restaurant_id=restaurant.restaurant_id, department=dept)
            db.add(target)
            existing[dept] = target
            inserted += 1
        else:
            updated += 1
        target.daily_hours_required = hours
    db.flush()

    log(f"  Department targets: {inserted} inserted, {updated} updated ({len(rows)} rows read)")


def main():
    parser = argparse.ArgumentParser(description="Import weekly_workflow/state CSVs into scheduler_db")
    parser.add_argument("--state-dir", required=True, help="Path to weekly_workflow/state")
    parser.add_argument("--restaurant-name", default="The Dwarf House")
    parser.add_argument("--dry-run", action="store_true",
                         help="Parse and report, but roll back instead of committing")
    args = parser.parse_args()

    employees_path = os.path.join(args.state_dir, "employees.csv")
    availability_path = os.path.join(args.state_dir, "availability.csv")
    shift_requirements_path = os.path.join(args.state_dir, "shift_requirements.csv")
    targets_path = os.path.join(args.state_dir, "targets.csv")

    db = SessionLocal()
    try:
        log(f"[1/5] Restaurant: {args.restaurant_name}")
        restaurant, created = get_or_create_restaurant(db, args.restaurant_name)
        log(f"  {'Created new' if created else 'Reusing existing'} restaurant_id={restaurant.restaurant_id}")

        log("[2/5] Roles...")
        employee_rows = read_csv(employees_path)
        shift_req_rows = read_csv(shift_requirements_path)
        role_names = set()
        for row in employee_rows:
            role_names.update(r.strip() for r in row["roles"].split(";") if r.strip())
        role_names.update(row["role"].strip() for row in shift_req_rows if row["role"].strip())
        roles_by_name, created_roles = get_or_create_roles(db, restaurant, role_names)
        log(f"  {len(roles_by_name)} roles total ({created_roles} newly created)")

        log("[3/5] Employees...")
        employees_by_ext_id = import_employees(db, restaurant, roles_by_name, employees_path)

        log("[4/5] Availability...")
        with open(availability_path, newline="", encoding="utf-8-sig") as f:
            availability_text = f.read()
        header = next(csv.reader(io.StringIO(availability_text)))
        if is_wide_availability_format(header):
            employees_by_name = {
                f"{e.first_name} {e.last_name}".lower(): e for e in employees_by_ext_id.values()
            }
            import_availability_wide(db, employees_by_name, availability_text)
        else:
            import_availability(db, employees_by_ext_id, read_csv(availability_path))

        log("[5/5] Shift requirements + department targets...")
        import_shift_requirements(db, restaurant, roles_by_name, shift_requirements_path)
        import_targets(db, restaurant, targets_path)

        if args.dry_run:
            db.rollback()
            log("\n[DRY RUN] Rolled back -- no changes were committed.")
        else:
            db.commit()
            log("\nDone -- changes committed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
