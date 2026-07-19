"""
time_utils.py
==============
Small shared helpers for day-name <-> day_of_week conversion and "HH:MM"
time parsing, used by both scheduler.py and the ScheduleConstraint
subclasses whose parameter_json references days/times (e.g.
PreferredAssignmentConstraint's "day": "Wed").

Uses the same Sun=0..Sat=6 convention as the availability/shift_templates
day_of_week columns and app.scripts.import_weekly_workflow.
"""

from datetime import datetime

DAY_TO_INT = {"Sun": 0, "Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6}


def normalize_day(s):
    day = s.strip()[:3].capitalize()
    if day not in DAY_TO_INT:
        raise ValueError(f"Unrecognized day '{s}'")
    return day


def day_of_week_from_name(s):
    return DAY_TO_INT[normalize_day(s)]


def day_of_week_from_date(d):
    """Python's date.weekday() is Mon=0..Sun=6; convert to Sun=0..Sat=6."""
    return (d.weekday() + 1) % 7


def parse_time(s):
    return datetime.strptime(s.strip(), "%H:%M").time()


def minutes_between(date1, time1, date2, time2):
    """Minutes from (date1, time1) to (date2, time2), which may be negative
    if the second point is earlier."""
    dt1 = datetime.combine(date1, time1)
    dt2 = datetime.combine(date2, time2)
    return (dt2 - dt1).total_seconds() / 60


def shift_hours(start_time, end_time):
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60  # overnight shift
    return (end_minutes - start_minutes) / 60.0
