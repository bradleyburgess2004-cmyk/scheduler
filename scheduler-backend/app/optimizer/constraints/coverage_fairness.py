from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.constraints.weights import hourly_penalty_rate

DEFAULT_WEIGHT = 50  # "Medium" preset -- used only if weight is somehow unset


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
