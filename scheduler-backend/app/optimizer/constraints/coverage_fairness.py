from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.constraints.weights import hourly_penalty_rate
from app.optimizer.time_utils import day_of_week_from_name

DEFAULT_WEIGHT = 50  # "Medium" preset -- used only if weight is somehow unset

# Role names containing any of these (case-insensitive) count as
# "leadership" -- avoids needing a hand-curated pool of specific
# employees; any role whose title says it's a leadership role qualifies
# automatically, including new roles added later.
LEADERSHIP_KEYWORDS = ["manager", "mgr", "director", "leader", "supervisor"]

# Fixed, not user-configurable -- mirrors how shift coverage shortfall
# (scheduler.py's SHORTFALL_PENALTY) is a heavy-but-finite penalty
# rather than a true hard constraint, so an unusual day (everyone with
# a leadership role is unavailable) can't make the whole week
# unsolvable.
LEADERSHIP_SHORTFALL_PENALTY = 1_000_000


def _is_leadership_role_name(role_name):
    lowered = role_name.lower()
    return any(keyword in lowered for keyword in LEADERSHIP_KEYWORDS)


class MinLeadershipPresentConstraint(ScheduleConstraint):
    """Requires at least parameters['min_count'] employees working a
    leadership-titled role (role name containing "manager", "mgr",
    "director", "leader", or "supervisor") to be assigned some shift on
    parameters['day'] (any role-matching shift, any time that day).

    Implemented as a heavily-penalized shortfall rather than a true
    hard constraint -- same safety reasoning as shift coverage
    requirements: this should almost always be satisfiable, but must
    not make the whole week's solve infeasible on a day where it
    genuinely can't be.
    """

    class_name = "MinLeadershipPresentConstraint"
    required_parameters = ["day", "min_count"]

    def apply(self, model, context):
        day_of_week = day_of_week_from_name(self.parameters["day"])
        min_count = self.parameters["min_count"]

        leadership_role_ids = {
            role_id
            for role_name, role_id in context.role_id_by_name.items()
            if _is_leadership_role_name(role_name)
        }
        if not leadership_role_ids:
            return  # this restaurant has no role that looks like a leadership title

        candidates = [
            context.x[(eid, sid)]
            for (eid, sid) in context.x
            if context.shifts[sid].day_of_week == day_of_week
            and context.shifts[sid].role_id in leadership_role_ids
        ]
        if not candidates:
            return

        covered = model.NewIntVar(0, len(candidates), "leadership_covered")
        model.Add(covered == sum(candidates))
        shortfall = model.NewIntVar(0, min_count, "leadership_shortfall")
        model.Add(covered + shortfall >= min_count)
        context.objective_terms.append(shortfall * LEADERSHIP_SHORTFALL_PENALTY)


class FairHoursDistributionConstraint(ScheduleConstraint):
    """Penalizes large hour disparities between similarly-available
    employees, by minimizing (max total hours - min total hours) across
    everyone with at least one eligible shift this week."""

    class_name = "FairHoursDistributionConstraint"
    required_parameters = []

    def apply(self, model, context):
        rate = hourly_penalty_rate(self.weight if self.weight is not None else DEFAULT_WEIGHT)
        eligible_employees = [
            eid for eid in context.employees if context.shift_ids_by_employee.get(eid)
        ]
        if len(eligible_employees) < 2:
            return

        max_possible_minutes = round(sum(s.hours * 60 for s in context.shifts.values()))
        totals = []
        for eid in eligible_employees:
            total = model.NewIntVar(0, max_possible_minutes, f"total_minutes_{eid}")
            model.Add(total == sum(
                context.x[(eid, sid)] * round(context.shifts[sid].hours * 60)
                for sid in context.shift_ids_by_employee[eid]
            ))
            totals.append(total)

        max_total = model.NewIntVar(0, max_possible_minutes, "hours_max")
        min_total = model.NewIntVar(0, max_possible_minutes, "hours_min")
        model.AddMaxEquality(max_total, totals)
        model.AddMinEquality(min_total, totals)

        spread = model.NewIntVar(0, max_possible_minutes, "hours_spread")
        model.Add(spread == max_total - min_total)
        context.objective_terms.append(spread * rate)


class EqualWeekendRotationConstraint(ScheduleConstraint):
    """Rotates which employees get weekend/holiday shifts over a
    parameters['lookback_weeks']-week window.

    NOTE: not implemented -- this needs historical `assignments` data
    from prior weeks to know whose "turn" it is, and the database has no
    schedule history yet (every prior solve's assignments get replaced,
    not archived). Meaningful once a few weeks have actually been solved
    and saved.
    """

    class_name = "EqualWeekendRotationConstraint"
    required_parameters = ["lookback_weeks"]


class DepartmentLaborBudgetConstraint(ScheduleConstraint):
    """Penalizes scheduled labor cost that exceeds a department's
    department_targets budget.

    NOTE: not implemented -- there's no role -> department mapping
    stored anywhere in scheduler_db (weekly_workflow's ROLE_TO_DEPT is a
    hardcoded Python dict inside run_week.py, never persisted). Without
    that mapping there's no way to group scheduled cost by department.
    """

    class_name = "DepartmentLaborBudgetConstraint"
    required_parameters = []
