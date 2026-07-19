"""
loader.py
==========
Reads the ENABLED restaurant_constraints rows for a restaurant and
instantiates the matching ScheduleConstraint subclass for each one,
using registry.CONSTRAINT_REGISTRY to resolve constraints.class_name to
a Python class.

This is the piece that "configures the LP solver constraints selected
by the caller" -- it does not build or run any solver itself. Whatever
eventually builds the CP-SAT model calls load_constraints_for_restaurant()
and calls .apply(model, context) on each result.
"""

from app.models.restaurant_constraint import RestaurantConstraint
from app.optimizer.constraints.registry import CONSTRAINT_REGISTRY


class UnknownConstraintError(Exception):
    """Raised when a restaurant_constraints row references a
    constraints.class_name with no registered ScheduleConstraint
    subclass -- fails loudly rather than silently skipping a rule the
    caller believes is active."""


def load_constraints_for_restaurant(db, restaurant_id):
    """Return a list of ScheduleConstraint instances for every rule
    enabled for this restaurant, ready to be handed to the solver."""
    rows = (
        db.query(RestaurantConstraint)
        .filter(
            RestaurantConstraint.restaurant_id == restaurant_id,
            RestaurantConstraint.enabled.is_(True),
        )
        .all()
    )

    constraints = []
    for row in rows:
        class_name = row.constraint.class_name
        constraint_cls = CONSTRAINT_REGISTRY.get(class_name)
        if constraint_cls is None:
            raise UnknownConstraintError(
                f"No registered ScheduleConstraint for class_name={class_name!r} "
                f"(restaurant_constraints.config_id={row.config_id})"
            )
        constraints.append(constraint_cls(
            restaurant_id=restaurant_id,
            enabled=row.enabled,
            weight=row.weight,
            parameters=row.parameter_json,
        ))
    return constraints
