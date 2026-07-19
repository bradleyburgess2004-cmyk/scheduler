/** Only these 4 constraints have a genuinely soft mode today -- their
 * weight actually changes solver behavior (see
 * app/optimizer/constraints/weights.py on the backend for the matching
 * normalized conversion). Every other constraint either ignores
 * weight entirely (always hard) or has no working apply() yet, so
 * showing a weight input for them would be misleading. */
export const SOFT_WITH_PRIORITY = new Set([
  'MinWeeklyHoursGuaranteeConstraint',
  'FairHoursDistributionConstraint',
  'PreferredAssignmentConstraint',
  'AvoidSplitShiftsConstraint',
])

export const PRIORITY_PRESETS = {
  low: 10,
  medium: 50,
  high: 200,
} as const

export type PriorityLevel = keyof typeof PRIORITY_PRESETS

export function priorityLevelForWeight(weight: number | null): PriorityLevel | 'custom' {
  if (weight === PRIORITY_PRESETS.low) return 'low'
  if (weight === PRIORITY_PRESETS.medium) return 'medium'
  if (weight === PRIORITY_PRESETS.high) return 'high'
  return 'custom'
}
