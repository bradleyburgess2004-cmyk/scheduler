from app.optimizer.constraints.base import ScheduleConstraint


def _validate_id_pairs(pairs, constraint_name):
    if not isinstance(pairs, list) or not pairs:
        raise ValueError(
            f"{constraint_name} requires a non-empty list of employee_id_pairs"
        )
    for pair in pairs:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            raise ValueError(
                f"{constraint_name}: each entry in employee_id_pairs must be a "
                f"2-element [employee_id, employee_id] pair, got {pair!r}"
            )


def _forbid_shared_shifts(model, context, employee_id_1, employee_id_2):
    shared_shift_ids = set(context.shift_ids_by_employee.get(employee_id_1, [])) & \
        set(context.shift_ids_by_employee.get(employee_id_2, []))
    for sid in shared_shift_ids:
        model.Add(context.x[(employee_id_1, sid)] + context.x[(employee_id_2, sid)] <= 1)


class CannotWorkWithConstraint(ScheduleConstraint):
    """Employees listed in parameters['employee_id_pairs'] must never be
    scheduled on the same shift (personal conflict, disciplinary
    separation, etc.)."""

    class_name = "CannotWorkWithConstraint"
    required_parameters = ["employee_id_pairs"]

    def validate_parameters(self):
        super().validate_parameters()
        _validate_id_pairs(self.parameters["employee_id_pairs"], type(self).__name__)

    def apply(self, model, context):
        for e1, e2 in self.parameters["employee_id_pairs"]:
            _forbid_shared_shifts(model, context, e1, e2)


class MustWorkWithConstraint(ScheduleConstraint):
    """parameters['primary_employee_id'] must always be scheduled
    alongside parameters['companion_employee_id'] (e.g. trainee +
    trainer). If the companion isn't even eligible for a given shift,
    the primary can't be assigned to it either."""

    class_name = "MustWorkWithConstraint"
    required_parameters = ["primary_employee_id", "companion_employee_id"]

    def apply(self, model, context):
        primary = self.parameters["primary_employee_id"]
        companion = self.parameters["companion_employee_id"]
        companion_shift_ids = set(context.shift_ids_by_employee.get(companion, []))
        for sid in context.shift_ids_by_employee.get(primary, []):
            if sid in companion_shift_ids:
                model.Add(context.x[(primary, sid)] <= context.x[(companion, sid)])
            else:
                model.Add(context.x[(primary, sid)] == 0)
