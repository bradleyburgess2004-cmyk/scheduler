from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.constraints.weights import occurrence_penalty_rate
from app.optimizer.time_utils import day_of_week_from_name, parse_time

DEFAULT_WEIGHT = 50  # "Medium" preset -- used only if weight is somehow unset


class PreferredAssignmentConstraint(ScheduleConstraint):
    """Rewards assigning parameters['employee_id'] to a shift matching
    parameters['role'] on any day in parameters['days'] (a list of day
    names, e.g. ["Mon", "Tue", "Wed", "Thu", "Fri"] for "every weekday"),
    optionally within parameters.get('start_time')-parameters.get('end_time').
    DB analog of weekly_workflow's preferred_assignments.csv.

    parameters['day'] (a single day name) is also still accepted for
    rows created before multi-day support existed -- treated as a
    one-item days list.
    """

    class_name = "PreferredAssignmentConstraint"
    required_parameters = ["role", "employee_id"]

    def validate_parameters(self):
        super().validate_parameters()
        if not self.parameters.get("days") and not self.parameters.get("day"):
            raise ValueError(
                f"{type(self).__name__} requires either 'days' (a list of day names) "
                "or 'day' (a single day name)"
            )

    def apply(self, model, context):
        rate = occurrence_penalty_rate(self.weight if self.weight is not None else DEFAULT_WEIGHT)
        eid = self.parameters["employee_id"]
        role_id = context.role_id_by_name.get(self.parameters["role"])
        if role_id is None:
            return  # this restaurant has no role by that name -- nothing to reward

        day_names = self.parameters.get("days") or [self.parameters["day"]]
        days_of_week = {day_of_week_from_name(d) for d in day_names}
        start_param = self.parameters.get("start_time")
        end_param = self.parameters.get("end_time")
        pref_start = parse_time(start_param) if start_param else None
        pref_end = parse_time(end_param) if end_param else None

        for sid in context.shift_ids_by_employee.get(eid, []):
            shift = context.shifts[sid]
            if shift.role_id != role_id or shift.day_of_week not in days_of_week:
                continue
            if pref_start is not None and not (
                shift.start_time <= pref_start and shift.end_time >= pref_end
            ):
                continue
            # negative because the overall objective is minimized -- a
            # satisfied preference should reduce cost, not add to it
            context.objective_terms.append(context.x[(eid, sid)] * -rate)


class AvoidSplitShiftsConstraint(ScheduleConstraint):
    """Penalizes scheduling the same employee for two separate shifts on
    the same calendar date with an actual gap between them (back-to-back
    or overlapping shifts aren't split shifts)."""

    class_name = "AvoidSplitShiftsConstraint"
    required_parameters = []

    def apply(self, model, context):
        rate = occurrence_penalty_rate(self.weight if self.weight is not None else DEFAULT_WEIGHT)
        for eid in context.employees:
            shift_ids = context.shift_ids_by_employee.get(eid, [])
            by_date = {}
            for sid in shift_ids:
                by_date.setdefault(context.shifts[sid].shift_date, []).append(sid)

            for shift_date, sids in by_date.items():
                if len(sids) < 2:
                    continue
                for i in range(len(sids)):
                    for j in range(i + 1, len(sids)):
                        s1, s2 = context.shifts[sids[i]], context.shifts[sids[j]]
                        earlier, later = (s1, s2) if s1.start_time <= s2.start_time else (s2, s1)
                        if later.start_time <= earlier.end_time:
                            continue  # overlapping or back-to-back -- not a split
                        both = model.NewBoolVar(f"split_{eid}_{sids[i]}_{sids[j]}")
                        model.AddMultiplicationEquality(
                            both, [context.x[(eid, sids[i])], context.x[(eid, sids[j])]]
                        )
                        context.objective_terms.append(both * rate)
