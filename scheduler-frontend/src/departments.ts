/** Shared department taxonomy -- mirrors roles.department in the DB.
 * Used by the Schedule page (grouping) and the Position Staffing
 * constraint manager (department picker) so both stay in sync. */
export const DEPARTMENT_ORDER = [
  'Back of House',
  'Full Service',
  'Self Service',
  'Other',
  'Training',
  'Leadership',
]

export const DEPARTMENT_LABELS: Record<string, string> = {
  'Back of House': 'BOH',
  'Full Service': 'Full Serve',
  'Self Service': 'Self Service',
  Other: 'Other',
  Training: 'Training',
  Leadership: 'Leadership',
}
