"""
store_hours.py
================
ModifiedStoreHoursConstraint: overrides normal operating hours for
either a specific calendar date (a one-time override, e.g. a holiday)
or a recurring day of week (e.g. every Sunday closes early).
"""

from datetime import date as date_type

from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.time_utils import day_of_week_from_name, parse_time


class ModifiedStoreHoursConstraint(ScheduleConstraint):
    """parameters:
        date: a specific calendar date (YYYY-MM-DD) this override applies
              to -- e.g. a holiday. Mutually exclusive with 'day'.
        day: a day name (e.g. "Sun") this override applies to every week
             -- e.g. a standing early close on Sundays. Mutually
             exclusive with 'date'. Exactly one of 'date'/'day' is
             required.
        closed: if true, no employee may be assigned to any shift on the
                matching date(s) at all.
        modified_start_time / modified_end_time: required unless
            'closed' is true -- the only window shifts may be staffed
            in on the matching date(s). Any shift starting before
            modified_start_time or ending after modified_end_time gets
            no assignments.

    NOTE: this only prevents assignments to affected shifts -- it does
    not remove or shrink the underlying Shift rows, since shifts are
    materialized from ShiftTemplate rows before constraints are loaded
    (see materialize_shifts_for_week in scheduler.py). A shift that
    falls entirely outside the modified window will still count toward
    coverage-shortfall like any other unstaffed shift; avoid having
    shift templates scheduled during known-closed windows if that
    shortfall noise matters.
    """

    class_name = "ModifiedStoreHoursConstraint"
    required_parameters = []

    def validate_parameters(self):
        super().validate_parameters()
        has_date = bool(self.parameters.get("date"))
        has_day = bool(self.parameters.get("day"))
        if has_date == has_day:
            raise ValueError(
                f"{type(self).__name__} requires exactly one of 'date' (a specific "
                "calendar date) or 'day' (a recurring day of week), not both or neither"
            )
        if not self.parameters.get("closed"):
            missing = [
                k for k in ("modified_start_time", "modified_end_time")
                if not self.parameters.get(k)
            ]
            if missing:
                raise ValueError(
                    f"{type(self).__name__} requires {missing} unless 'closed' is true"
                )

    def apply(self, model, context):
        date_param = self.parameters.get("date")
        day_param = self.parameters.get("day")
        closed = bool(self.parameters.get("closed"))

        target_date = date_type.fromisoformat(date_param) if date_param else None
        target_day_of_week = day_of_week_from_name(day_param) if day_param else None
        modified_start = parse_time(self.parameters["modified_start_time"]) if not closed else None
        modified_end = parse_time(self.parameters["modified_end_time"]) if not closed else None

        for (eid, sid), var in context.x.items():
            shift = context.shifts[sid]
            if target_date is not None and shift.shift_date != target_date:
                continue
            if target_day_of_week is not None and shift.day_of_week != target_day_of_week:
                continue
            if closed:
                model.Add(var == 0)
            elif shift.start_time < modified_start or shift.end_time > modified_end:
                model.Add(var == 0)
