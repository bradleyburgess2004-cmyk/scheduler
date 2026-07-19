import type { FieldSpec } from './constraintFormSpecs'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`Request failed: ${response.status} ${body}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json()
}

export interface Restaurant {
  restaurant_id: number
  name: string
  location: string | null
  timezone: string | null
  created_at: string | null
}

export function getRestaurants(): Promise<Restaurant[]> {
  return request('/restaurants/')
}

export interface Role {
  role_id: number
  restaurant_id: number
  role_name: string
  department: string | null
}

export function getRoles(): Promise<Role[]> {
  return request('/roles/')
}

export interface EmployeeRole {
  employee_id: number
  role_id: number
}

export function getEmployeeRoles(): Promise<EmployeeRole[]> {
  return request('/employee-roles/')
}

export function createEmployeeRole(input: EmployeeRole): Promise<EmployeeRole> {
  return request('/employee-roles/', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function deleteEmployeeRole(employeeId: number, roleId: number): Promise<void> {
  return request(`/employee-roles/${employeeId}/${roleId}`, { method: 'DELETE' })
}

export interface Employee {
  employee_id: number
  restaurant_id: number
  first_name: string
  last_name: string
  role_id: number | null
  hourly_rate: string | null
  hire_date: string | null
  active: boolean
  max_weekly_hours: number | null
  overtime_limit: number | null
  external_employee_id: string | null
  min_weekly_hours: number | null
}

export interface EmployeeInput {
  restaurant_id: number
  first_name: string
  last_name: string
  role_id?: number | null
  active?: boolean
  hourly_rate?: number | null
  hire_date?: string | null
  max_weekly_hours?: number | null
  overtime_limit?: number | null
  min_weekly_hours?: number | null
}

export function getEmployees(): Promise<Employee[]> {
  return request('/employees/')
}

export function createEmployee(input: EmployeeInput): Promise<Employee> {
  return request('/employees/', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateEmployee(employeeId: number, input: EmployeeInput): Promise<Employee> {
  return request(`/employees/${employeeId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function deleteEmployee(employeeId: number): Promise<void> {
  return request(`/employees/${employeeId}`, { method: 'DELETE' })
}

export interface Availability {
  availability_id: number
  employee_id: number
  day_of_week: number
  start_time: string
  end_time: string
  availability_date: string | null
}

export function getAvailability(): Promise<Availability[]> {
  return request('/availability/')
}

export interface ScheduledShift {
  assignment_id: number
  shift_id: number
  role_id: number
  role_name: string
  start_time: string
  end_time: string
  hours: number
  required_employees: number
  understaffed: boolean
}

export interface EmployeeDay {
  date: string
  shifts: ScheduledShift[]
}

export interface EmployeeScheduleRow {
  employee_id: number
  first_name: string
  last_name: string
  role_id: number | null
  role_name: string | null
  department: string | null
  hourly_rate: number
  total_hours: number
  total_cost: number
  days: EmployeeDay[]
}

export interface DailyTotal {
  date: string
  headcount: number
  cost: number
  understaffed_shifts: number
}

export interface ScheduleResponse {
  restaurant_id: number
  week_start: string
  week_dates: string[]
  employees: EmployeeScheduleRow[]
  daily_totals: DailyTotal[]
  week_total_cost: number
  week_total_assignments: number
  week_understaffed_shifts: number
}

export function getSchedule(restaurantId: number, weekStart: string): Promise<ScheduleResponse> {
  return request(`/restaurants/${restaurantId}/schedule?week_start=${weekStart}`)
}

export interface GenerateScheduleResult {
  restaurant_id: number
  week_start: string
  assignments_saved: number
  total_cost: number
  understaffed_shifts: number
  locked_assignments_skipped: number
}

export function generateSchedule(restaurantId: number, weekStart: string): Promise<GenerateScheduleResult> {
  return request(`/restaurants/${restaurantId}/schedule/generate?week_start=${weekStart}`, {
    method: 'POST',
  })
}

export interface AssignmentInput {
  shift_id: number
  employee_id: number
}

export function updateAssignment(assignmentId: number, input: AssignmentInput): Promise<unknown> {
  return request(`/assignments/${assignmentId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function deleteAssignment(assignmentId: number): Promise<void> {
  return request(`/assignments/${assignmentId}`, { method: 'DELETE' })
}

export interface ShiftInput {
  restaurant_id: number
  role_id: number
  shift_date: string
  start_time: string
  end_time: string
  required_employees?: number | null
}

export function updateShift(shiftId: number, input: ShiftInput): Promise<unknown> {
  return request(`/shifts/${shiftId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export interface ConstraintCatalogItem {
  constraint_id: number
  name: string
  description: string | null
  class_name: string | null
  parameter_spec: FieldSpec[] | null
}

export function getConstraints(): Promise<ConstraintCatalogItem[]> {
  return request('/constraints/')
}

export interface RestaurantConstraint {
  config_id: number
  restaurant_id: number
  constraint_id: number
  enabled: boolean | null
  weight: number | null
  parameter_json: Record<string, unknown> | null
}

export interface RestaurantConstraintInput {
  restaurant_id: number
  constraint_id: number
  enabled: boolean | null
  weight: number | null
  parameter_json: Record<string, unknown> | null
}

export function getRestaurantConstraints(): Promise<RestaurantConstraint[]> {
  return request('/restaurant-constraints/')
}

export function createRestaurantConstraint(input: RestaurantConstraintInput): Promise<RestaurantConstraint> {
  return request('/restaurant-constraints/', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateRestaurantConstraint(
  configId: number,
  input: RestaurantConstraintInput
): Promise<RestaurantConstraint> {
  return request(`/restaurant-constraints/${configId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function deleteRestaurantConstraint(configId: number): Promise<void> {
  return request(`/restaurant-constraints/${configId}`, { method: 'DELETE' })
}

export interface WeeklyLaborSummary {
  week_start: string
  total_cost: number
  total_assignments: number
  understaffed_shifts: number
  total_shifts: number
}

export interface DepartmentCostBreakdown {
  department: string
  cost: number
  hours: number
  assignments: number
}

export interface LaborAnalyticsResponse {
  restaurant_id: number
  weekly_trend: WeeklyLaborSummary[]
  breakdown_week_start: string | null
  department_breakdown: DepartmentCostBreakdown[]
}

export function getLaborAnalytics(
  restaurantId: number,
  options?: { weeks?: number; weekStart?: string }
): Promise<LaborAnalyticsResponse> {
  const params = new URLSearchParams()
  if (options?.weeks) params.set('weeks', String(options.weeks))
  if (options?.weekStart) params.set('week_start', options.weekStart)
  const query = params.toString()
  return request(`/restaurants/${restaurantId}/labor-analytics${query ? `?${query}` : ''}`)
}

export interface AvailabilityUploadResult {
  rows_read: number
  employees_updated: number
  windows_applied: number
  orphaned_employee_ids: string[]
  unmatched_names: string[]
  created_employees: string[]
}

export async function uploadAvailability(
  restaurantId: number,
  file: File,
  autoCreateEmployees: boolean
): Promise<AvailabilityUploadResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('auto_create_employees', String(autoCreateEmployees))

  // Not using request() here -- it always forces
  // Content-Type: application/json, which breaks multipart uploads.
  // The browser sets the correct multipart boundary header itself as
  // long as we don't set Content-Type manually.
  const response = await fetch(`${API_BASE_URL}/restaurants/${restaurantId}/availability/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`Upload failed: ${response.status} ${body}`)
  }
  return response.json()
}

export interface TimeOffRecord {
  employee_name: string
  employee_id: number | null
  start_date: string
  end_date: string
  status: string
}

export async function parseTimeOffReport(restaurantId: number, file: File): Promise<TimeOffRecord[]> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/restaurants/${restaurantId}/time-off/parse`, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`Parse failed: ${response.status} ${body}`)
  }
  const data = await response.json()
  return data.records
}

export interface TimeOffApplyResult {
  days_blocked: number
  requests_applied: number
  requests_skipped_not_approved: number
  requests_skipped_unmatched: number
}

export function applyTimeOffRecords(restaurantId: number, records: TimeOffRecord[]): Promise<TimeOffApplyResult> {
  return request(`/restaurants/${restaurantId}/time-off/apply`, {
    method: 'POST',
    body: JSON.stringify({ records }),
  })
}

export interface ConstraintProposal {
  action: 'configure_constraint'
  constraint_id: number | null
  class_name: string
  constraint_name: string | null
  existing_config_id: number | null
  enabled: boolean
  weight: number | null
  parameter_json: Record<string, unknown>
  validation_errors: string[]
  warnings: string[]
}

export interface ScheduleGenerationProposal {
  action: 'generate_schedule'
  week_start: string
  time_limit: number
  validation_errors: string[]
  warnings: string[]
}

export type AiProposal = ConstraintProposal | ScheduleGenerationProposal

export function interpretAiPrompt(restaurantId: number, prompt: string): Promise<{ proposal: AiProposal }> {
  return request(`/restaurants/${restaurantId}/ai/interpret`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

export function confirmAiProposal(restaurantId: number, proposal: AiProposal): Promise<unknown> {
  return request(`/restaurants/${restaurantId}/ai/confirm`, {
    method: 'POST',
    body: JSON.stringify(proposal),
  })
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface PendingSchedule {
  week_start: string
  time_limit: number
}

export interface AiChatResult {
  reply: string
  applied: boolean
  pending_schedule: PendingSchedule | null
}

export function chatWithAi(restaurantId: number, message: string, history: ChatTurn[]): Promise<AiChatResult> {
  return request(`/restaurants/${restaurantId}/ai/chat`, {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  })
}
