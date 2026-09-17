"""
registry.py
============
Maps constraints.class_name (from the DB catalog) to the Python class
that implements it, so the loader can instantiate the right
ScheduleConstraint subclass for each enabled restaurant_constraints row.

Every class added to a category file must also be added to
_CONSTRAINT_CLASSES here, or it will silently be unreachable from the
DB -- load_constraints_for_restaurant() raises UnknownConstraintError
rather than skip a row quietly, so a missing registration surfaces
immediately instead of a rule the caller thinks is active being ignored.
"""

from app.optimizer.constraints.hour_limits import (
    MaxWeeklyHoursConstraint,
    MinWeeklyHoursGuaranteeConstraint,
    MaxConsecutiveDaysConstraint,
    MinRestBetweenShiftsConstraint,
    MaxHoursPerShiftConstraint,
    MaxShiftsPerWeekConstraint,
    RequiredMealBreakConstraint,
)
from app.optimizer.constraints.legal import (
    MinorAgeRestrictionConstraint,
    CertificationRequiredConstraint,
    RoleEligibilityConstraint,
)
from app.optimizer.constraints.availability_policies import (
    CanWorkNightsConstraint,
    CanWorkWeekendsConstraint,
    CanWorkHolidaysConstraint,
)
from app.optimizer.constraints.relationships import (
    CannotWorkWithConstraint,
    MustWorkWithConstraint,
)
from app.optimizer.constraints.coverage_fairness import (
    FairHoursDistributionConstraint,
    EqualWeekendRotationConstraint,
    DepartmentLaborBudgetConstraint,
)
from app.optimizer.constraints.preferences import (
    PreferredAssignmentConstraint,
    AvoidSplitShiftsConstraint,
)
from app.optimizer.constraints.locks import (
    LockedAssignmentConstraint,
)
from app.optimizer.constraints.position_staffing import (
    MinPositionStaffingConstraint,
)
from app.optimizer.constraints.store_hours import (
    ModifiedStoreHoursConstraint,
)

_CONSTRAINT_CLASSES = [
    MaxWeeklyHoursConstraint,
    MinWeeklyHoursGuaranteeConstraint,
    MaxConsecutiveDaysConstraint,
    MinRestBetweenShiftsConstraint,
    MaxHoursPerShiftConstraint,
    MaxShiftsPerWeekConstraint,
    RequiredMealBreakConstraint,
    MinorAgeRestrictionConstraint,
    CertificationRequiredConstraint,
    RoleEligibilityConstraint,
    CanWorkNightsConstraint,
    CanWorkWeekendsConstraint,
    CanWorkHolidaysConstraint,
    CannotWorkWithConstraint,
    MustWorkWithConstraint,
    FairHoursDistributionConstraint,
    EqualWeekendRotationConstraint,
    DepartmentLaborBudgetConstraint,
    PreferredAssignmentConstraint,
    AvoidSplitShiftsConstraint,
    LockedAssignmentConstraint,
    MinPositionStaffingConstraint,
    ModifiedStoreHoursConstraint,
]

CONSTRAINT_REGISTRY = {cls.class_name: cls for cls in _CONSTRAINT_CLASSES}
