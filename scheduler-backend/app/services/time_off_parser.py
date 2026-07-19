"""
time_off_parser.py
=====================
Parses a raw, copy-pasted "Time Off & Request Report" export (a messy
PDF/webpage text dump, not a real CSV -- repeating table headers,
multi-line free-text fields, employee names appearing once followed by
1+ requests) into structured records. This is a text-extraction task
with too much irregularity for a hand-written parser to be reliable, so
it's handed to Claude with a narrow tool schema: Claude only extracts
facts explicitly present in the text (employee name, date range,
status) and never decides what happens to them -- every actual
database write happens in plain Python in
app/routes/time_off_upload.py, after the caller has reviewed the
parsed records (the same preview-then-confirm pattern as the AI
assistant's schedule-generation flow).
"""

from collections import defaultdict
from datetime import date, timedelta

from app.models.availability import Availability
from app.models.employee import Employee
from app.optimizer.time_utils import day_of_week_from_date
from app.services.ai_assistant import get_client, MODEL

EXTRACT_TIME_OFF_TOOL = {
    "name": "extract_time_off_records",
    "description": (
        "Extract every time-off request record found in the report text. The report "
        "lists an employee's full name once, followed by one or more requests for that "
        "employee, until the next employee's name appears. Ignore repeated table header "
        "rows (lines like 'Date and Time Type Employee Reason Employee Comments Submitted "
        "Status Approval Manager Manager Comments Status Change' that repeat due to "
        "pagination) -- they are not data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "employee_name": {
                            "type": "string",
                            "description": "The employee's full name exactly as written.",
                        },
                        "start_date": {
                            "type": "string",
                            "description": (
                                "The first date of the request, as YYYY-MM-DD. Two-digit "
                                "years are 20XX (e.g. 7/23/26 -> 2026-07-23). For an 'All "
                                "Day' single-date request, start_date and end_date are the same."
                            ),
                        },
                        "end_date": {
                            "type": "string",
                            "description": (
                                "The last date of the request, as YYYY-MM-DD -- the date "
                                "after 'Through' for a range, or the same as start_date for "
                                "a single 'All Day' request."
                            ),
                        },
                        "status": {
                            "type": "string",
                            "enum": ["Approved", "Denied", "Canceled", "Pending Approval"],
                            "description": "The Status column value for this request, exactly as shown.",
                        },
                    },
                    "required": ["employee_name", "start_date", "end_date", "status"],
                },
            },
        },
        "required": ["records"],
    },
}

SYSTEM_PROMPT = (
    "You extract structured data from a raw, copy-pasted 'Time Off & Request Report' "
    "text export. It is not clean CSV -- it's plain text copied from a rendered report, "
    "so lines wrap unpredictably (e.g. a reason or a manager's name can split across two "
    "lines) and the table header repeats every time the source document paginated. Your "
    "only job is to find every actual time-off request record and extract exactly what's "
    "written: the employee it belongs to, its date range, and its status. Do not invent, "
    "infer, or guess anything not present in the text. Call extract_time_off_records "
    "exactly once with every record you find."
)


def parse_time_off_report(db, restaurant_id: int, raw_text: str) -> list[dict]:
    """Returns a list of dicts: employee_name, employee_id (resolved
    against this restaurant's roster, None if unmatched), start_date,
    end_date (both date objects), status. Read-only -- makes no writes."""

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[EXTRACT_TIME_OFF_TOOL],
        tool_choice={"type": "tool", "name": "extract_time_off_records"},
        messages=[{"role": "user", "content": raw_text}],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    raw_records = tool_use.input.get("records", [])

    employees = db.query(Employee).filter(Employee.restaurant_id == restaurant_id).all()
    employees_by_name = {f"{e.first_name} {e.last_name}".strip().lower(): e for e in employees}

    records = []
    for r in raw_records:
        try:
            start_date = date.fromisoformat(r["start_date"])
            end_date = date.fromisoformat(r["end_date"])
        except (KeyError, ValueError):
            continue
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        name = r.get("employee_name", "").strip()
        emp = employees_by_name.get(name.lower())

        records.append({
            "employee_name": name,
            "employee_id": emp.employee_id if emp else None,
            "start_date": start_date,
            "end_date": end_date,
            "status": r.get("status", ""),
        })

    return records


def apply_time_off_day(db, employee_id: int, blocked_date: date) -> None:
    """Marks a single specific date as unavailable for an employee (one
    day of an approved time-off request), overriding whatever
    availability existed for that date.

    load_availability() (app/optimizer/scheduler.py) only trusts an
    employee's dated rows for a week if there's at least one dated row
    somewhere in that week -- otherwise it falls back to their
    day-of-week recurring pattern for the whole week. If this employee
    has no dated coverage at all for the week blocked_date falls in,
    inserting a single isolated "blocked" marker would flip that whole
    week into dated-only mode and make every OTHER day look unavailable
    too (since nothing else that week would have a dated row). To avoid
    that, this backfills the other 6 days of the week from the
    employee's legacy day-of-week pattern first (a no-op if the week
    already has dated coverage, e.g. from a recent CSV upload), then
    clears blocked_date itself -- zero dated rows on that one date, with
    the rest of the week now dated too, correctly reads as unavailable
    only on that date.

    Does not commit -- caller commits once after applying every date in
    a request."""

    monday = blocked_date - timedelta(days=blocked_date.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    # Flush before checking -- this session runs with autoflush disabled
    # (app/database.py), and callers apply a multi-day request one date
    # at a time via repeated calls to this function. Without an explicit
    # flush here, a still-pending (un-flushed) backfill INSERT from an
    # earlier date in the same request/week -- or a still-pending
    # DELETE -- wouldn't be visible to this query or to the DELETE
    # below, which would both under-count "does this week have dated
    # coverage yet" and let an earlier date's backfill row for a LATER
    # blocked date in the same request survive uncleared.
    db.flush()

    has_dated_coverage_this_week = (
        db.query(Availability)
        .filter(
            Availability.employee_id == employee_id,
            Availability.availability_date.in_(week_dates),
        )
        .first()
        is not None
    )

    if not has_dated_coverage_this_week:
        legacy_rows = (
            db.query(Availability)
            .filter(Availability.employee_id == employee_id, Availability.availability_date.is_(None))
            .all()
        )
        legacy_by_dow = defaultdict(list)
        for a in legacy_rows:
            legacy_by_dow[a.day_of_week].append(a)

        for d in week_dates:
            if d == blocked_date:
                continue
            for a in legacy_by_dow.get(day_of_week_from_date(d), []):
                db.add(Availability(
                    employee_id=employee_id,
                    day_of_week=a.day_of_week,
                    start_time=a.start_time,
                    end_time=a.end_time,
                    availability_date=d,
                ))

    db.query(Availability).filter(
        Availability.employee_id == employee_id,
        Availability.availability_date == blocked_date,
    ).delete(synchronize_session=False)
