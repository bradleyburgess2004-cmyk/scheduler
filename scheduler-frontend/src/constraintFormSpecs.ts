/** Field types for constraint parameters -- the actual per-class_name
 * field specs now come from the API (`ConstraintCatalogItem.parameter_spec`,
 * sourced from the backend's app/optimizer/constraints/param_specs.py,
 * the single canonical schema shared with the AI assistant). This file
 * only keeps the shared TS types and day-select options that
 * ParameterField.tsx needs.
 *
 * `key` must match the parameter_json key the backend actually reads.
 * `type` drives which widget renders:
 *   number         -> numeric input
 *   time           -> HH:MM input
 *   day            -> Sun..Sat select
 *   role           -> select of this restaurant's role names
 *   employee       -> select of this restaurant's employees (by id)
 *   text           -> free text (used only where there's genuinely no
 *                     existing data to pick from, e.g. pool/skill names)
 *   employee_pairs -> repeatable add/remove list of employee-pair rows
 *   day_multi      -> multi-select checkboxes of Sun..Sat (value is a list of day names)
 *   date           -> a specific calendar date (YYYY-MM-DD)
 *   boolean        -> a single checkbox
 *   requirement_list -> repeatable list of {day, start_time, end_time,
 *                     min_count} rows (MinPositionStaffingConstraint only --
 *                     rendered by the bespoke PositionStaffingManager, not ParameterField)
 */

export type FieldType =
  | 'number'
  | 'time'
  | 'day'
  | 'role'
  | 'employee'
  | 'text'
  | 'employee_pairs'
  | 'day_multi'
  | 'date'
  | 'boolean'
  | 'requirement_list'

export interface FieldSpec {
  key: string
  label: string
  type: FieldType
  optional?: boolean
}

export const DAY_OPTIONS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
