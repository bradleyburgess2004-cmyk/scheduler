"""
schedule_template_parser.py
=============================
Parses a "wide" schedule-template CSV (one row per employee, one column
per day of week, each cell either blank/OFF or an "HH:MM-HH:MM" shift
window) into reviewable ScheduleTemplateEntryOut records, and persists a
reviewed set as a ScheduleTemplate + ScheduleTemplateEntry rows.

Mirrors the wide-format availability parsing in
app/scripts/import_weekly_workflow.py (employee matching by
external_employee_id or lowercased "first last" name) and the
parse-then-apply review flow used by app/services/time_off_parser.py.
"""

import csv
import io
import re

from app.models.employee import Employee
from app.models.schedule_template import ScheduleTemplate
from app.models.schedule_template_entry import ScheduleTemplateEntry
from app.optimizer.time_utils import day_of_week_from_name
from app.optimizer.time_utils import parse_time
from app.schemas.schedule_template import DAY_NAMES
from app.schemas.schedule_template import ScheduleTemplateEntryOut
from app.schemas.schedule_template import ScheduleTemplateParseResponse

_SKIP_CELLS = {"", "off", "-", "n/a"}
_SHIFT_CELL_RE = re.compile(r"^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$")


def parse_schedule_template_csv(db, restaurant_id, text) -> ScheduleTemplateParseResponse:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("File is empty")

    day_cols = []
    for col_index, cell in enumerate(header[1:], start=1):
        try:
            day_cols.append((col_index, day_of_week_from_name(cell)))
        except ValueError:
            continue
    if not day_cols:
        raise ValueError("No recognizable day-of-week columns found in header")

    employees = db.query(Employee).filter(Employee.restaurant_id == restaurant_id).all()
    employees_by_ext_id = {e.external_employee_id: e for e in employees if e.external_employee_id}
    employees_by_name = {f"{e.first_name} {e.last_name}".lower(): e for e in employees}

    entries = []
    unmatched_labels = set()
    unparsed_cells = []
    rows_read = 0

    for row_index, row in enumerate(reader, start=2):
        if not row or not row[0].strip():
            continue
        rows_read += 1

        label = row[0].strip()
        emp = employees_by_ext_id.get(label) or employees_by_name.get(label.lower())
        if emp is None:
            unmatched_labels.add(label)

        for col_index, day_of_week in day_cols:
            if col_index >= len(row):
                continue
            cell = row[col_index].strip()
            if cell.lower() in _SKIP_CELLS:
                continue
            if not _SHIFT_CELL_RE.match(cell):
                unparsed_cells.append(f"row {row_index} ({label}), {DAY_NAMES[day_of_week]}: '{cell}'")
                continue

            start_str, end_str = [p.strip() for p in cell.split("-", 1)]
            try:
                start_time = parse_time(start_str)
                end_time = parse_time(end_str)
            except ValueError:
                unparsed_cells.append(f"row {row_index} ({label}), {DAY_NAMES[day_of_week]}: '{cell}'")
                continue
            if end_time <= start_time:
                unparsed_cells.append(f"row {row_index} ({label}), {DAY_NAMES[day_of_week]}: '{cell}'")
                continue

            entries.append(ScheduleTemplateEntryOut(
                raw_employee_label=label,
                employee_id=emp.employee_id if emp else None,
                employee_name=f"{emp.first_name} {emp.last_name}" if emp else None,
                day_of_week=day_of_week,
                day_name=DAY_NAMES[day_of_week],
                start_time=start_time,
                end_time=end_time,
            ))

    return ScheduleTemplateParseResponse(
        rows_read=rows_read,
        entries=entries,
        unmatched_labels=sorted(unmatched_labels),
        unparsed_cells=unparsed_cells,
    )


def save_schedule_template(db, restaurant_id, name, entries) -> ScheduleTemplate:
    """Persists the (possibly user-edited) reviewed entries. Entries
    with no resolved employee_id are dropped -- they can't be matched
    against anyone's shifts, so keeping them around would just be dead
    weight. Caller is responsible for db.commit()."""
    template = ScheduleTemplate(restaurant_id=restaurant_id, name=name)
    db.add(template)
    db.flush()

    for entry in entries:
        if entry.employee_id is None:
            continue
        db.add(ScheduleTemplateEntry(
            template_id=template.template_id,
            employee_id=entry.employee_id,
            day_of_week=entry.day_of_week,
            start_time=entry.start_time,
            end_time=entry.end_time,
        ))

    db.flush()
    return template
