from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.constraints.weights import hourly_penalty_rate
from app.optimizer.time_utils import minutes_between

DEFAULT_WEIGHT = 50  # "Medium" preset -- used only if weight is somehow unset


class MaxWeeklyHoursConstraint(ScheduleConstraint):
    """Caps each employee's total scheduled hours at their
    employees.max_weekly_hours."""

    class_name = "MaxWeeklyHoursConstraint"
    required_parameters = []

    def apply(self, model, context):
        for eid, emp in context.employees.items():
            if emp.max_weekly_hours is None:
                continue
            shift_ids = context.shift_ids_by_employee.get(eid, [])
            if not shift_ids:
                continue
            total_minutes = sum(
                context.x[(eid, sid)] * round(context.shifts[sid].hours * 60)
                for sid in shift_ids
            )
            model.Add(total_minutes <= round(emp.max_weekly_hours * 60))


class MinWeeklyHoursGuaranteeConstraint(ScheduleConstraint):
    """Rewards scheduling each employee at least their
    employees.min_weekly_hours -- a soft floor, not a hard requirement
    (there may simply not be enough eligible shifts to hit it)."""

    class_name = "MinWeeklyHoursGuaranteeConstraint"
    required_parameters = []

    def apply(self, model, context):
        rate = hourly_penalty_rate(self.weight if self.weight is not None else DEFAULT_WEIGHT)
        for eid, emp in context.employees.items():
            if not emp.min_weekly_hours:
                continue
            shift_ids = context.shift_ids_by_employee.get(eid, [])
            if not shift_ids:
                continue
            min_minutes = round(emp.min_weekly_hours * 60)
            total_minutes = sum(
                context.x[(eid, sid)] * round(context.shifts[sid].hours * 60)
                for sid in shift_ids
            )
            shortfall = model.NewIntVar(0, min_minutes, f"min_hours_shortfall_{eid}")
            model.Add(total_minutes + shortfall >= min_minutes)
            context.objective_terms.append(shortfall * rate)


class MaxConsecutiveDaysConstraint(ScheduleConstraint):
    """No more than parameters['max_days'] days worked in a row, checked
    via a sliding window over the calendar dates in the shifts being
    solved. Only tracks consecutive days within the current solve's date
    range -- a multi-week streak spanning two separate solves isn't
    tracked yet."""

    class_name = "MaxConsecutiveDaysConstraint"
    required_parameters = ["max_days"]

    def apply(self, model, context):
        max_days = self.parameters["max_days"]
        all_dates = sorted({s.shift_date for s in context.shifts.values()})
        if len(all_dates) <= max_days:
            return
        for eid in context.employees:
            shift_ids = context.shift_ids_by_employee.get(eid, [])
            if not shift_ids:
                continue
            worked_by_date = {}
            for d in all_dates:
                sids_that_day = [sid for sid in shift_ids if context.shifts[sid].shift_date == d]
                if not sids_that_day:
                    worked_by_date[d] = 0
                    continue
                worked = model.NewBoolVar(f"worked_{eid}_{d.isoformat()}")
                model.AddMaxEquality(worked, [context.x[(eid, sid)] for sid in sids_that_day])
                worked_by_date[d] = worked
            for start_idx in range(len(all_dates) - max_days):
                window = all_dates[start_idx:start_idx + max_days + 1]
                model.Add(sum(worked_by_date[d] for d in window) <= max_days)


class MinRestBetweenShiftsConstraint(ScheduleConstraint):
    """At least parameters['min_rest_hours'] between the end of one
    shift and the start of an employee's next shift (prevents
    clopening)."""

    class_name = "MinRestBetweenShiftsConstraint"
    required_parameters = ["min_rest_hours"]

    def apply(self, model, context):
        min_rest_minutes = round(self.parameters["min_rest_hours"] * 60)
        for eid in context.employees:
            shift_ids = context.shift_ids_by_employee.get(eid, [])
            shifts = [context.shifts[sid] for sid in shift_ids]
            for i in range(len(shifts)):
                for j in range(len(shifts)):
                    if i == j:
                        continue
                    s1, s2 = shifts[i], shifts[j]
                    if (s2.shift_date, s2.start_time) <= (s1.shift_date, s1.start_time):
                        continue  # only consider each ordered pair once (s1 before s2)
                    gap = minutes_between(s1.shift_date, s1.end_time, s2.shift_date, s2.start_time)
                    if gap < min_rest_minutes:
                        model.Add(context.x[(eid, s1.shift_id)] + context.x[(eid, s2.shift_id)] <= 1)


class MaxHoursPerShiftConstraint(ScheduleConstraint):
    """No single shift may exceed parameters['max_hours'] for an
    employee -- enforced by excluding the assignment outright rather
    than a model.Add, since a shift's length is fixed, not a variable."""

    class_name = "MaxHoursPerShiftConstraint"
    required_parameters = ["max_hours"]

    def apply(self, model, context):
        max_hours = self.parameters["max_hours"]
        for (eid, sid), var in context.x.items():
            if context.shifts[sid].hours > max_hours:
                model.Add(var == 0)


class MaxShiftsPerWeekConstraint(ScheduleConstraint):
    """Caps the number of shift instances (not total hours) per week at
    parameters['max_shifts']."""

    class_name = "MaxShiftsPerWeekConstraint"
    required_parameters = ["max_shifts"]

    def apply(self, model, context):
        max_shifts = self.parameters["max_shifts"]
        for eid in context.employees:
            shift_ids = context.shift_ids_by_employee.get(eid, [])
            if not shift_ids:
                continue
            model.Add(sum(context.x[(eid, sid)] for sid in shift_ids) <= max_shifts)


class RequiredMealBreakConstraint(ScheduleConstraint):
    """Requires an unpaid break of parameters['break_minutes'] once a
    shift exceeds parameters['threshold_hours'].

    NOTE: not implemented -- this is a shift-generation-time concern
    (splitting a long shift around a break), not something that can be
    expressed as a constraint over whole-shift assignment variables the
    way the model is currently structured.
    """

    class_name = "RequiredMealBreakConstraint"
    required_parameters = ["threshold_hours", "break_minutes"]
