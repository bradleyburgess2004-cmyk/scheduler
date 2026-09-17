"""
template_adherence.py
=======================
Softly biases the solver toward reproducing a saved ScheduleTemplate's
(employee, day, time) pattern for the week being solved. Unlike every
other ScheduleConstraint here, this one is NOT loaded from the
`restaurant_constraints` DB catalog via registry.py/param_specs.py --
it's an ephemeral, per-generate-call input built directly by
solve_schedule() from an optional template_id argument, with
(employee, shift) pairs already resolved to this week's actual shifts
by the caller (see scheduler.py's build_template_matches()).

Deliberately a soft reward (context.objective_terms), never a hard
model.Add(var == 1) like LockedAssignmentConstraint -- a template is
built from a *past* week and is expected to conflict with this week's
availability/time-off/coverage/hour-limit rules sometimes. Forcing it
would risk making the model infeasible; rewarding it lets every other
rule still win whenever they actually conflict.
"""

from app.optimizer.constraints.base import ScheduleConstraint
from app.optimizer.constraints.weights import occurrence_penalty_rate

DEFAULT_TEMPLATE_WEIGHT = 30  # dollars-per-honored-shift, same order of magnitude as PreferredAssignmentConstraint.DEFAULT_WEIGHT


class TemplateAdherenceConstraint(ScheduleConstraint):

    class_name = "TemplateAdherenceConstraint"
    required_parameters = ["matched_shift_ids_by_employee"]

    def apply(self, model, context):
        rate = occurrence_penalty_rate(self.weight if self.weight is not None else DEFAULT_TEMPLATE_WEIGHT)
        for eid, shift_ids in self.parameters["matched_shift_ids_by_employee"].items():
            for sid in shift_ids:
                var = context.x.get((eid, sid))
                if var is None:
                    continue  # not eligible this week (unavailable/role mismatch) -- silently skipped
                # negative because the overall objective is minimized -- honoring
                # the template should reduce cost, not add to it
                context.objective_terms.append(var * -rate)
