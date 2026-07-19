"""
base.py
========
ScheduleConstraint is the common interface every specific scheduling
rule (hour_limits.py, legal.py, etc.) implements. Each instance
represents one ENABLED restaurant_constraints row, resolved to its
Python class via registry.CONSTRAINT_REGISTRY and ready to be handed to
the solver.

The actual OR-Tools model-building logic (apply()) is intentionally not
implemented yet -- only the class structure, parameter validation, and
the hard/soft distinction. Subclasses fill in apply() once the CP-SAT
model construction exists.
"""


class ScheduleConstraint:

    # Must match a row's constraints.class_name in the DB catalog.
    class_name = None

    # parameter_json keys this constraint requires to function.
    required_parameters = []

    def __init__(self, restaurant_id, enabled, weight, parameters):
        self.restaurant_id = restaurant_id
        self.enabled = enabled
        self.weight = weight
        self.parameters = parameters or {}
        self.validate_parameters()

    def validate_parameters(self):
        """Subclasses with extra shape requirements (e.g. a list of
        employee_id pairs) should call super() then add their own
        checks, raising ValueError with a clear message."""
        missing = [p for p in self.required_parameters if p not in self.parameters]
        if missing:
            raise ValueError(
                f"{type(self).__name__} is missing required parameter(s): {missing}"
            )

    @property
    def is_hard(self):
        """Hard constraints must never be violated and ignore weight.
        Soft constraints use weight as their penalty in the solver's
        objective function. Convention: weight is None -> hard."""
        return self.weight is None

    def apply(self, model, context):
        """Add this constraint's effect to the CP-SAT model being built.

        `model` will be the ortools cp_model.CpModel instance. `context`
        will be whatever shared solver state (employees, shifts,
        decision variables, etc.) the model-building code passes in --
        its shape isn't defined yet, since the solver itself hasn't been
        built. Subclasses will translate `self.parameters` into
        model.Add(...) constraints or objective cost terms here.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.apply() is not implemented yet"
        )

    def __repr__(self):
        return (
            f"<{type(self).__name__} enabled={self.enabled} "
            f"weight={self.weight} parameters={self.parameters}>"
        )
