"""
weights.py
===========
Normalizes what a soft constraint's `weight` actually means. The
solver's objective is tracked in cents (see scheduler.py's cost_terms:
hourly_rate * hours * 100), so a `weight` needs converting into the
same units before it can be compared against real labor cost or
against another constraint's weight.

`weight` is defined as an approximate dollar value, in one of two
denominations depending on what a constraint's violation naturally is:

    hourly_penalty_rate(weight)     -- for violations measured in
                                        minutes (a shortfall, a spread)
    occurrence_penalty_rate(weight) -- for violations measured as a
                                        flat per-instance count/boolean

Only the constraints that are genuinely soft today use these
(MinWeeklyHoursGuaranteeConstraint, FairHoursDistributionConstraint,
PreferredAssignmentConstraint, AvoidSplitShiftsConstraint) -- everything
else is a hard rule and doesn't read `weight` at all.
"""


def hourly_penalty_rate(weight):
    """Converts a 'dollars per hour of violation' weight into a
    per-minute cents coefficient, usable directly as a multiplier
    against a violation-in-minutes IntVar."""
    return max(1, round(weight * 100 / 60))


def occurrence_penalty_rate(weight):
    """Converts a 'dollars per occurrence' weight into a cents
    coefficient, usable directly as a multiplier against a
    violation-count/boolean IntVar."""
    return round(weight * 100)
