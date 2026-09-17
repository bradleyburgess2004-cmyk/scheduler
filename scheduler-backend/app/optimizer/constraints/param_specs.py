"""
param_specs.py
================
Canonical, typed parameter schema per constraint class_name. This is
the single source of truth both the AI assistant service and the
`GET /constraints` API response draw from -- previously this shape only
existed as a hand-maintained duplicate in the frontend
(scheduler-frontend/src/constraintFormSpecs.ts). Keep this file and
CONSTRAINT_REGISTRY (registry.py) in sync: every registered class_name
must have an entry here, enforced by the assertion at the bottom of
this module.

`key` must match the parameter_json key the backend actually reads
(see each class's `required_parameters` and `apply()` in the sibling
constraint modules). `type` drives which widget the frontend renders:
    number         -> numeric input
    time           -> HH:MM input
    day            -> Sun..Sat select
    role           -> select of this restaurant's role names (value is
                      the role_name string, not role_id -- constraints
                      look roles up by name via context.role_id_by_name)
    employee       -> select of this restaurant's employees (value is
                      the integer employee_id)
    text           -> free text (used only where there's genuinely no
                      existing data to pick from, e.g. skill names)
    employee_pairs -> repeatable list of [employee_id, employee_id] pairs
    requirement_list -> repeatable list of {days, start_time, end_time,
                      min_count} rows, where days is a list of day names
                      (MinPositionStaffingConstraint only)
    day_multi      -> multi-select of Sun..Sat (value is a list of day names)
    date           -> a specific calendar date (YYYY-MM-DD)
    boolean        -> a single checkbox
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    type: str
    optional: bool = False


CONSTRAINT_PARAM_SPECS: dict[str, list[FieldSpec]] = {
    "MaxWeeklyHoursConstraint": [],
    "MinWeeklyHoursGuaranteeConstraint": [],
    "MaxConsecutiveDaysConstraint": [
        FieldSpec("max_days", "Max consecutive days", "number"),
    ],
    "MinRestBetweenShiftsConstraint": [
        FieldSpec("min_rest_hours", "Minimum rest between shifts (hours)", "number"),
    ],
    "MaxHoursPerShiftConstraint": [
        FieldSpec("max_hours", "Max hours per shift", "number"),
    ],
    "MaxShiftsPerWeekConstraint": [
        FieldSpec("max_shifts", "Max shifts per week", "number"),
    ],
    "RequiredMealBreakConstraint": [
        FieldSpec("threshold_hours", "Shift length that requires a break (hours)", "number"),
        FieldSpec("break_minutes", "Break length (minutes)", "number"),
    ],
    "MinorAgeRestrictionConstraint": [
        FieldSpec("min_age", "Minimum age", "number"),
        FieldSpec("latest_end_time", "Latest shift end time", "time"),
        FieldSpec("max_hours_school_night", "Max hours on a school night", "number", optional=True),
    ],
    "CertificationRequiredConstraint": [
        FieldSpec("role", "Role requiring certification", "role"),
        FieldSpec("required_skill", "Required certification name", "text"),
    ],
    "RoleEligibilityConstraint": [],
    "CanWorkNightsConstraint": [
        FieldSpec("night_start", "Night window start", "time"),
        FieldSpec("night_end", "Night window end", "time"),
    ],
    "CanWorkWeekendsConstraint": [],
    "CanWorkHolidaysConstraint": [],
    "CannotWorkWithConstraint": [
        FieldSpec("employee_id_pairs", "Employees who can never share a shift", "employee_pairs"),
    ],
    "MustWorkWithConstraint": [
        FieldSpec("primary_employee_id", "Employee", "employee"),
        FieldSpec("companion_employee_id", "Must always be scheduled with", "employee"),
    ],
    "FairHoursDistributionConstraint": [],
    "EqualWeekendRotationConstraint": [
        FieldSpec("lookback_weeks", "Look-back window (weeks)", "number"),
    ],
    "DepartmentLaborBudgetConstraint": [],
    "PreferredAssignmentConstraint": [
        FieldSpec("days", "Days (e.g. every weekday morning)", "day_multi"),
        FieldSpec("role", "Role", "role"),
        FieldSpec("employee_id", "Employee", "employee"),
        FieldSpec("start_time", "Start time", "time", optional=True),
        FieldSpec("end_time", "End time", "time", optional=True),
    ],
    "AvoidSplitShiftsConstraint": [],
    "LockedAssignmentConstraint": [
        FieldSpec("days", "Days (e.g. every weekday morning)", "day_multi"),
        FieldSpec("role", "Role", "role"),
        FieldSpec("employee_id", "Employee to lock in", "employee"),
        FieldSpec("start_time", "Start time", "time", optional=True),
        FieldSpec("end_time", "End time", "time", optional=True),
    ],
    "MinPositionStaffingConstraint": [
        FieldSpec("position_type", "Position type (role or department)", "text"),
        FieldSpec("position_value", "Role or department name", "text"),
        FieldSpec("requirements", "Day/time/count requirements", "requirement_list"),
    ],
    "ModifiedStoreHoursConstraint": [
        FieldSpec("date", "Specific date (one-time override, e.g. a holiday)", "date", optional=True),
        FieldSpec("day", "Recurring day of week (e.g. every Sunday)", "day", optional=True),
        FieldSpec("closed", "Store closed all day", "boolean", optional=True),
        FieldSpec("modified_start_time", "Modified opening time", "time", optional=True),
        FieldSpec("modified_end_time", "Modified closing time", "time", optional=True),
    ],
}


# Field types that identify "which row" a constraint instance is about
# (a specific employee, role, day, or date). A class with at least one
# field of these types can meaningfully have more than one row per
# restaurant -- e.g. one MustWorkWithConstraint row per pair of
# employees, one ModifiedStoreHoursConstraint row per date override.
# Everything else is a singleton (a plain number/boolean knob like "max
# 5 consecutive days"): at most one row per restaurant makes sense, so
# the Constraints page doesn't offer "+ Add rule" for it. Also used by
# app/services/ai_assistant.py to disambiguate which existing row an AI
# proposal should update.
IDENTITY_FIELD_TYPES = {"employee", "role", "day", "date"}

# MinPositionStaffingConstraint's identifying field (position_value) is
# typed "text" like several non-identifying fields on other classes, so
# it can't be inferred purely from field type -- explicit override.
EXPLICIT_MULTI_ROW_CLASSES = {"MinPositionStaffingConstraint"}


def supports_multiple_rows(class_name: str) -> bool:
    """Whether more than one restaurant_constraints row for this
    class_name is meaningful (see IDENTITY_FIELD_TYPES above) -- drives
    whether the Constraints page shows "+ Add rule" for it."""
    if class_name in EXPLICIT_MULTI_ROW_CLASSES:
        return True
    return any(f.type in IDENTITY_FIELD_TYPES for f in CONSTRAINT_PARAM_SPECS.get(class_name, []))


def _assert_specs_match_registry():
    # Imported lazily to avoid a circular import at module load time
    # (registry.py doesn't import param_specs, but keep this defensive).
    from app.optimizer.constraints.registry import CONSTRAINT_REGISTRY

    missing = [name for name in CONSTRAINT_REGISTRY if name not in CONSTRAINT_PARAM_SPECS]
    if missing:
        raise RuntimeError(
            f"CONSTRAINT_PARAM_SPECS is missing entries for registered constraint(s): {missing}"
        )


_assert_specs_match_registry()
