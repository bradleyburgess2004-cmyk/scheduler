from app.optimizer.constraints.base import ScheduleConstraint


class MinorAgeRestrictionConstraint(ScheduleConstraint):
    """Restricts scheduling for employees under parameters['min_age'] --
    e.g. no shift ending after parameters['latest_end_time'], and no
    more than parameters.get('max_hours_school_night') hours on a
    school night.

    NOTE: not enforceable today -- `employees` has no birth_date column,
    so there's no age data for this constraint to read yet.
    """

    class_name = "MinorAgeRestrictionConstraint"
    required_parameters = ["min_age", "latest_end_time"]


class CertificationRequiredConstraint(ScheduleConstraint):
    """Requires a valid credential (parameters['required_skill']) to be
    scheduled for parameters['role'].

    NOTE: the skills/employee_skills tables exist but are currently
    empty for real employees and have no expiration_date column, so
    "valid, non-expired" can't be fully checked -- only presence of the
    skill row. Until employee_skills gets populated, enabling this will
    exclude every employee from the given role (correct behavior given
    the data, just worth knowing before turning it on).
    """

    class_name = "CertificationRequiredConstraint"
    required_parameters = ["role", "required_skill"]

    def apply(self, model, context):
        role_id = context.role_id_by_name.get(self.parameters["role"])
        if role_id is None:
            return  # this restaurant has no role by that name -- nothing to restrict
        required_skill = self.parameters["required_skill"]
        for (eid, sid), var in context.x.items():
            if context.shifts[sid].role_id != role_id:
                continue
            if required_skill not in context.employee_skill_names.get(eid, set()):
                model.Add(var == 0)


class RoleEligibilityConstraint(ScheduleConstraint):
    """An employee may only be scheduled for shifts matching one of
    their assigned roles (employee_roles). Already effectively enforced
    by how eligible (employee, shift) pairs get built in the solver --
    ineligible-role pairs never get a decision variable in the first
    place -- so this is a no-op, cataloged so it can be reported on."""

    class_name = "RoleEligibilityConstraint"
    required_parameters = []

    def apply(self, model, context):
        return
