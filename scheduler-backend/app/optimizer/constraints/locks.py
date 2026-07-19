from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.time_utils import day_of_week_from_name, parse_time


class LockedAssignmentConstraint(ScheduleConstraint):
    """Hard-forces parameters['employee_id'] onto every shift matching
    parameters['role'] on any day in parameters['days'] (a list of day
    names -- same shape as PreferredAssignmentConstraint), optionally
    narrowed to parameters.get('start_time')-parameters.get('end_time').

    Unlike PreferredAssignmentConstraint (a soft objective nudge), this
    forces x[(employee_id, shift_id)] == 1 in CP-SAT for every matching
    shift -- the employee WILL be on that shift, full stop. weight is
    ignored entirely; a lock is always hard regardless of what's stored
    in restaurant_constraints.weight.

    The one thing that can still keep a locked employee off a shift is
    availability (or a role mismatch): build_eligible_assignment_vars()
    only creates a decision variable for (employee, shift) pairs the
    employee is actually eligible for, so if they're unavailable that
    day there's no variable to force. Those cases are silently skipped
    here and recorded on context.skipped_locks so the caller can report
    back which locks didn't take, instead of the solver just going
    infeasible with no explanation.

    parameters['day'] (a single day name) is also still accepted for
    rows created before multi-day support existed -- treated as a
    one-item days list.
    """

    class_name = "LockedAssignmentConstraint"
    required_parameters = ["role", "employee_id"]

    def validate_parameters(self):
        super().validate_parameters()
        if not self.parameters.get("days") and not self.parameters.get("day"):
            raise ValueError(
                f"{type(self).__name__} requires either 'days' (a list of day names) "
                "or 'day' (a single day name)"
            )

    def apply(self, model, context):
        eid = self.parameters["employee_id"]
        role_id = context.role_id_by_name.get(self.parameters["role"])
        if role_id is None:
            return  # this restaurant has no role by that name -- nothing to lock

        day_names = self.parameters.get("days") or [self.parameters["day"]]
        days_of_week = {day_of_week_from_name(d) for d in day_names}
        start_param = self.parameters.get("start_time")
        end_param = self.parameters.get("end_time")
        lock_start = parse_time(start_param) if start_param else None
        lock_end = parse_time(end_param) if end_param else None

        for sid, shift in context.shifts.items():
            if shift.role_id != role_id or shift.day_of_week not in days_of_week:
                continue
            if lock_start is not None and not (
                shift.start_time <= lock_start and shift.end_time >= lock_end
            ):
                continue

            var = context.x.get((eid, sid))
            if var is None:
                context.skipped_locks.append((eid, sid))
                continue
            model.Add(var == 1)
