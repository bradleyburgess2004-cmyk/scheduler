from app.optimizer.constraints.base import ScheduleConstraint


class CanWorkNightsConstraint(ScheduleConstraint):
    """Standing opt-out from shifts starting/ending within the night
    window (parameters['night_start']..parameters['night_end']),
    independent of week-to-week `availability` rows.

    NOTE: not implemented -- this parameter shape defines what "night"
    means restaurant-wide, but there's nowhere to record WHICH employees
    are opted out. Needs either an employee-level flag/column or an
    `excluded_employee_ids` list added to parameters before this can
    apply per-person rather than to everyone.
    """

    class_name = "CanWorkNightsConstraint"
    required_parameters = ["night_start", "night_end"]


class CanWorkWeekendsConstraint(ScheduleConstraint):
    """Standing opt-out/opt-in for weekend shifts.

    NOTE: not implemented -- same gap as CanWorkNightsConstraint: no
    per-employee opt-out data exists yet.
    """

    class_name = "CanWorkWeekendsConstraint"
    required_parameters = []


class CanWorkHolidaysConstraint(ScheduleConstraint):
    """Standing opt-out/opt-in for holiday shifts.

    NOTE: not implemented -- same gap as CanWorkNightsConstraint (no
    per-employee opt-out data), plus there's no `holidays` concept
    anywhere in scheduler_db to know which shift_date values even count
    as a holiday.
    """

    class_name = "CanWorkHolidaysConstraint"
    required_parameters = []
