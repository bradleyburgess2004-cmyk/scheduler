/** class_names whose apply() still raises NotImplementedError -- the
 * solver will skip these with a log warning rather than apply them.
 * Kept in sync with app/optimizer/constraints/*.py by hand. */
export const NOT_YET_IMPLEMENTED = new Set([
  'MinorAgeRestrictionConstraint',
  'CanWorkNightsConstraint',
  'CanWorkWeekendsConstraint',
  'CanWorkHolidaysConstraint',
  'EqualWeekendRotationConstraint',
  'DepartmentLaborBudgetConstraint',
  'RequiredMealBreakConstraint',
])
