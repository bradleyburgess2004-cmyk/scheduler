"""
position_staffing.py
======================
MinPositionStaffingConstraint: requires a minimum number of employees
in a specific role or an entire department present during one or more
day/time windows (e.g. "at least 5 in BOH on Saturday 5:00-11:00").

Unlike every other constraint, a manager needs several of these at
once (BOH mornings, Full Serve weekends, etc.), each for a different
position. Nothing stops multiple restaurant_constraints rows sharing
the same constraint_id (no DB uniqueness constraint on
(restaurant_id, constraint_id)), so each position gets its own row --
this class just needs to support a LIST of day/time/count requirements
within one row's parameters, one row per position.
"""

from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.time_utils import day_of_week_from_name, parse_time

# Fixed, not user-configurable -- this should almost always be
# satisfiable, but an unusual day/time combination must not make the
# whole week's solve infeasible.
POSITION_STAFFING_SHORTFALL_PENALTY = 1_000_000


class MinPositionStaffingConstraint(ScheduleConstraint):
    """parameters:
        position_type: "role" or "department"
        position_value: the exact role_name or department name to match
        requirements: list of {days, start_time, end_time, min_count},
            where days is a list of day names (e.g. ["Fri", "Sat"] to
            apply the same minimum to both days without a separate
            requirement row per day). A single-day legacy {day: "Sat",
            ...} shape (from before multi-day support existed) is also
            still accepted, treated as a one-item days list.

    "Present" means the employee's shift overlaps the window at all
    (not true continuous per-minute coverage). Implemented as a
    heavily-penalized shortfall per requirement per day, not a true
    hard constraint.
    """

    class_name = "MinPositionStaffingConstraint"
    required_parameters = ["position_type", "position_value", "requirements"]

    def validate_parameters(self):
        super().validate_parameters()
        if self.parameters["position_type"] not in ("role", "department"):
            raise ValueError("position_type must be 'role' or 'department'")
        requirements = self.parameters["requirements"]
        if not isinstance(requirements, list) or not requirements:
            raise ValueError("requirements must be a non-empty list")
        for req in requirements:
            missing = [k for k in ("start_time", "end_time", "min_count") if k not in req]
            if missing:
                raise ValueError(f"each requirement needs {missing}")
            if not req.get("days") and not req.get("day"):
                raise ValueError("each requirement needs either 'days' (a list of day names) or 'day'")

    def apply(self, model, context):
        position_type = self.parameters["position_type"]
        position_value = self.parameters["position_value"]

        if position_type == "role":
            matching_role_ids = {
                role_id
                for role_name, role_id in context.role_id_by_name.items()
                if role_name == position_value
            }
        else:
            matching_role_ids = set(context.role_ids_by_department.get(position_value, set()))

        if not matching_role_ids:
            return  # this restaurant has no role/department matching position_value

        # multiple position-staffing rules can be enabled at once (one
        # per position), so variable names need to disambiguate across
        # instances, not just across requirements within one instance
        tag = position_value.replace(" ", "_")

        for index, req in enumerate(self.parameters["requirements"]):
            day_names = req.get("days") or [req["day"]]
            window_start = parse_time(req["start_time"])
            window_end = parse_time(req["end_time"])
            min_count = req["min_count"]

            for day_name in day_names:
                day_of_week = day_of_week_from_name(day_name)

                candidates = [
                    context.x[(eid, sid)]
                    for (eid, sid) in context.x
                    if context.shifts[sid].day_of_week == day_of_week
                    and context.shifts[sid].role_id in matching_role_ids
                    and context.shifts[sid].start_time < window_end
                    and context.shifts[sid].end_time > window_start
                ]
                if not candidates:
                    continue

                covered = model.NewIntVar(0, len(candidates), f"position_staffing_covered_{tag}_{index}_{day_of_week}")
                model.Add(covered == sum(candidates))
                shortfall = model.NewIntVar(0, min_count, f"position_staffing_shortfall_{tag}_{index}_{day_of_week}")
                model.Add(covered + shortfall >= min_count)
                context.objective_terms.append(shortfall * POSITION_STAFFING_SHORTFALL_PENALTY)
