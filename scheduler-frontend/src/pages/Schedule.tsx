import { Fragment, useEffect, useMemo, useState } from 'react'
import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import {
  getSchedule,
  generateSchedule,
  getRoles,
  getAvailability,
  updateAssignment,
  deleteAssignment,
  updateShift,
  listScheduleTemplates,
  type ScheduleResponse,
  type ScheduledShift,
  type EmployeeScheduleRow,
  type Role,
  type Availability,
  type ScheduleTemplateSummary,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { addDays, formatDate, mondayOfWeek, parseLocalDate, weekdayLabel, shiftHours } from '../dateUtils'
import { recomputeSchedule } from '../scheduleRecompute'
import {
  DraggableShiftChip,
  DroppableCell,
  ShiftChipPreview,
  type ShiftEdit,
  type AvailabilityStatus,
} from '../components/ScheduleDnd'
import { SORT_OPTIONS, type SortKey } from '../sortUtils'
import { DEPARTMENT_ORDER, DEPARTMENT_LABELS } from '../departments'
import './Schedule.css'

function compareEmployees(a: EmployeeScheduleRow, b: EmployeeScheduleRow, sortKey: SortKey): number {
  const nameA = `${a.last_name} ${a.first_name}`
  const nameB = `${b.last_name} ${b.first_name}`
  if (sortKey === 'role') {
    return (a.role_name ?? '').localeCompare(b.role_name ?? '') || nameA.localeCompare(nameB)
  }
  if (sortKey === 'wage') {
    return b.hourly_rate - a.hourly_rate || nameA.localeCompare(nameB)
  }
  return nameA.localeCompare(nameB)
}

function parseCellId(id: string): { employeeId: number; date: string } | null {
  const parts = id.split(':')
  if (parts[0] !== 'cell') return null
  return { employeeId: Number(parts[1]), date: parts[2] }
}

function parseChipId(id: string): { employeeId: number; date: string; shiftId: number } | null {
  const parts = id.split(':')
  if (parts[0] !== 'chip') return null
  return { employeeId: Number(parts[1]), date: parts[2], shiftId: Number(parts[3]) }
}

function Schedule() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()
  const [weekStart, setWeekStart] = useState(() => mondayOfWeek(new Date()))
  const [schedule, setSchedule] = useState<ScheduleResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hideEmptyRows, setHideEmptyRows] = useState(true)
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [activeShift, setActiveShift] = useState<ScheduledShift | null>(null)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [lockWarning, setLockWarning] = useState<string | null>(null)
  const [roles, setRoles] = useState<Role[]>([])
  const [availability, setAvailability] = useState<Availability[]>([])
  const [showAvailability, setShowAvailability] = useState(true)
  const [templates, setTemplates] = useState<ScheduleTemplateSummary[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)
  const [templateWeight, setTemplateWeight] = useState(30)
  const [templateResultNote, setTemplateResultNote] = useState<string | null>(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  useEffect(() => {
    if (!restaurant) return
    setLoading(true)
    setError(null)
    getSchedule(restaurant.restaurant_id, formatDate(weekStart))
      .then(setSchedule)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [restaurant, weekStart])

  useEffect(() => {
    if (!restaurant) return
    getRoles()
      .then((roleList) => setRoles([...roleList].sort((a, b) => a.role_name.localeCompare(b.role_name))))
      .catch(() => {
        // Non-fatal -- the edit-role dropdown just won't have options if this fails.
      })
  }, [restaurant])

  useEffect(() => {
    if (!restaurant) return
    getAvailability()
      .then(setAvailability)
      .catch(() => {
        // Non-fatal -- the overlay just won't render if this fails.
      })
  }, [restaurant])

  useEffect(() => {
    if (!restaurant) return
    listScheduleTemplates(restaurant.restaurant_id)
      .then(setTemplates)
      .catch(() => {
        // Non-fatal -- the template picker just won't have options if this fails.
      })
  }, [restaurant])

  const availabilityByEmployee = useMemo(() => {
    const map = new Map<number, Availability[]>()
    for (const a of availability) {
      const list = map.get(a.employee_id) ?? []
      list.push(a)
      map.set(a.employee_id, list)
    }
    return map
  }, [availability])

  // Mirrors load_availability() in app/optimizer/scheduler.py: whether an
  // employee's DATED rows (from a wide-format/HotSchedules upload, or an
  // approved time-off override) apply is scoped per week being viewed,
  // not globally -- only if they have at least one dated row within
  // THIS week does that week resolve from dated rows alone (a date with
  // no matching row then means unavailable). An employee with dated
  // rows only for some other week still falls back to their undated
  // day-of-week pattern for this one, so an isolated dated row (e.g. a
  // single time-off day) never silently blacks out their whole week.
  function getAvailabilityInfo(
    employeeId: number,
    date: string
  ): { availabilityStatus: AvailabilityStatus; availabilityTitle?: string } {
    const windows = availabilityByEmployee.get(employeeId)
    if (!windows || windows.length === 0) return { availabilityStatus: 'unknown' }

    const weekDatesSet = new Set(schedule?.week_dates ?? [])
    const datedWindowsThisWeek = windows.filter(
      (w) => w.availability_date != null && weekDatesSet.has(w.availability_date)
    )
    const dayOfWeek = parseLocalDate(date).getDay()

    const relevantWindows = datedWindowsThisWeek.length > 0
      ? datedWindowsThisWeek.filter((w) => w.availability_date === date)
      : windows.filter((w) => w.day_of_week === dayOfWeek && w.availability_date == null)

    if (relevantWindows.length === 0) {
      return { availabilityStatus: 'unavailable', availabilityTitle: 'Not available this day' }
    }
    const ranges = relevantWindows.map((w) => `${w.start_time.slice(0, 5)}–${w.end_time.slice(0, 5)}`).join(', ')
    return { availabilityStatus: 'available', availabilityTitle: `Available ${ranges}` }
  }

  const visibleRows = useMemo(() => {
    if (!schedule) return []
    return schedule.employees
      .filter((e) => !hideEmptyRows || e.total_hours > 0)
      .filter((e) => {
        if (!search.trim()) return true
        const name = `${e.first_name} ${e.last_name}`.toLowerCase()
        return name.includes(search.trim().toLowerCase())
      })
  }, [schedule, hideEmptyRows, search])

  const groupedRows = useMemo(() => {
    const groups = new Map<string, EmployeeScheduleRow[]>()
    for (const emp of visibleRows) {
      const dept = emp.department ?? 'Other'
      if (!groups.has(dept)) groups.set(dept, [])
      groups.get(dept)!.push(emp)
    }
    for (const list of groups.values()) {
      list.sort((a, b) => compareEmployees(a, b, sortKey))
    }
    return DEPARTMENT_ORDER.filter((dept) => groups.has(dept)).map((dept) => ({
      department: dept,
      employees: groups.get(dept)!,
    }))
  }, [visibleRows, sortKey])

  function handleDragStart(event: DragStartEvent) {
    const data = event.active.data.current as { shift: ScheduledShift } | undefined
    setActiveShift(data?.shift ?? null)
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveShift(null)
    const { active, over } = event
    if (!over || !schedule) return

    const source = parseChipId(active.id.toString())
    const target = parseCellId(over.id.toString())
    if (!source || !target) return
    if (source.employeeId === target.employeeId) return
    if (source.date !== target.date) return // a shift's date is fixed -- only reassigning who covers it makes sense

    const srcEmp = schedule.employees.find((e) => e.employee_id === source.employeeId)
    const dstEmp = schedule.employees.find((e) => e.employee_id === target.employeeId)
    const srcDay = srcEmp?.days.find((d) => d.date === source.date)
    const dstDay = dstEmp?.days.find((d) => d.date === target.date)
    const movedShift = srcDay?.shifts.find((s) => s.shift_id === source.shiftId)
    if (!movedShift || !dstDay) return
    if (dstDay.shifts.some((s) => s.shift_id === source.shiftId)) return // already covering this shift

    setEditError(null)
    setEditSaving(true)
    try {
      await updateAssignment(movedShift.assignment_id, {
        shift_id: movedShift.shift_id,
        employee_id: target.employeeId,
      })
      setSchedule((prev) => {
        if (!prev) return prev
        const employees = prev.employees.map((e) => ({
          ...e,
          days: e.days.map((d) => ({ ...d, shifts: [...d.shifts] })),
        }))
        const srcEmp2 = employees.find((e) => e.employee_id === source.employeeId)!
        const dstEmp2 = employees.find((e) => e.employee_id === target.employeeId)!
        const srcDay2 = srcEmp2.days.find((d) => d.date === source.date)!
        const dstDay2 = dstEmp2.days.find((d) => d.date === target.date)!
        const shiftIndex = srcDay2.shifts.findIndex((s) => s.shift_id === source.shiftId)
        const [moved] = srcDay2.shifts.splice(shiftIndex, 1)
        dstDay2.shifts.push(moved)
        return recomputeSchedule({ ...prev, employees })
      })
    } catch (err) {
      setEditError(err instanceof Error ? err.message : String(err))
    } finally {
      setEditSaving(false)
    }
  }

  async function handleGenerate() {
    if (!restaurant) return
    setGenerating(true)
    setGenerateError(null)
    setLockWarning(null)
    setTemplateResultNote(null)
    try {
      const result = await generateSchedule(restaurant.restaurant_id, formatDate(weekStart), {
        templateId: selectedTemplateId,
        templateWeight: selectedTemplateId ? templateWeight : null,
      })
      const fresh = await getSchedule(restaurant.restaurant_id, formatDate(weekStart))
      setSchedule(fresh)
      if (result.locked_assignments_skipped > 0) {
        setLockWarning(
          `${result.locked_assignments_skipped} locked assignment(s) couldn't be honored -- ` +
          `the employee wasn't available (or eligible) for that shift.`
        )
      }
      if (result.template_id_used != null) {
        setTemplateResultNote(
          `Template applied: ${result.template_entries_applied} shift(s) matched this week` +
          (result.template_entries_unmatched > 0
            ? `, ${result.template_entries_unmatched} unmatched (no shift this week at that day/time/role).`
            : '.')
        )
      }
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : String(err))
    } finally {
      setGenerating(false)
    }
  }

  async function handleRemoveShift(employeeId: number, date: string, shiftId: number) {
    const emp = schedule?.employees.find((e) => e.employee_id === employeeId)
    const day = emp?.days.find((d) => d.date === date)
    const shift = day?.shifts.find((s) => s.shift_id === shiftId)
    if (!shift) return

    setEditError(null)
    setEditSaving(true)
    try {
      await deleteAssignment(shift.assignment_id)
      setSchedule((prev) => {
        if (!prev) return prev
        const employees = prev.employees.map((e) => ({
          ...e,
          days: e.days.map((d) => ({ ...d, shifts: [...d.shifts] })),
        }))
        const emp2 = employees.find((e) => e.employee_id === employeeId)!
        const day2 = emp2.days.find((d) => d.date === date)!
        day2.shifts = day2.shifts.filter((s) => s.shift_id !== shiftId)
        return recomputeSchedule({ ...prev, employees })
      })
    } catch (err) {
      setEditError(err instanceof Error ? err.message : String(err))
    } finally {
      setEditSaving(false)
    }
  }

  async function handleEditShift(employeeId: number, date: string, shiftId: number, edit: ShiftEdit) {
    if (!restaurant) return
    const emp = schedule?.employees.find((e) => e.employee_id === employeeId)
    const day = emp?.days.find((d) => d.date === date)
    const shift = day?.shifts.find((s) => s.shift_id === shiftId)
    if (!shift) return

    setEditError(null)
    setEditSaving(true)
    try {
      await updateShift(shiftId, {
        restaurant_id: restaurant.restaurant_id,
        role_id: edit.role_id,
        shift_date: date,
        start_time: edit.start_time,
        end_time: edit.end_time,
        required_employees: shift.required_employees,
      })
      setSchedule((prev) => {
        if (!prev) return prev
        const employees = prev.employees.map((e) => ({
          ...e,
          days: e.days.map((d) => ({ ...d, shifts: [...d.shifts] })),
        }))
        const emp2 = employees.find((e) => e.employee_id === employeeId)!
        const day2 = emp2.days.find((d) => d.date === date)!
        const shiftIndex = day2.shifts.findIndex((s) => s.shift_id === shiftId)
        day2.shifts[shiftIndex] = {
          ...day2.shifts[shiftIndex],
          start_time: edit.start_time,
          end_time: edit.end_time,
          role_id: edit.role_id,
          role_name: edit.role_name,
          hours: shiftHours(edit.start_time, edit.end_time),
        }
        return recomputeSchedule({ ...prev, employees })
      })
    } catch (err) {
      setEditError(err instanceof Error ? err.message : String(err))
    } finally {
      setEditSaving(false)
    }
  }

  if (restaurantLoading) return <p>Loading...</p>
  if (restaurantError) return <p className="form-error">{restaurantError}</p>

  const columnCount = (schedule?.week_dates.length ?? 7) + 3

  return (
    <div>
      <h1>Schedule</h1>

      <div className="schedule-controls">
        <button onClick={() => setWeekStart((d) => addDays(d, -7))}>&larr; Prev week</button>
        <input
          type="date"
          value={formatDate(weekStart)}
          onChange={(e) => setWeekStart(mondayOfWeek(parseLocalDate(e.target.value)))}
        />
        <button onClick={() => setWeekStart((d) => addDays(d, 7))}>Next week &rarr;</button>

        <input
          type="text"
          placeholder="Search employee..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <label className="schedule-toggle">
          Sort by
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>

        <label className="schedule-toggle">
          <input
            type="checkbox"
            checked={hideEmptyRows}
            onChange={(e) => setHideEmptyRows(e.target.checked)}
          />
          Hide employees with no shifts this week
        </label>

        <label className="schedule-toggle">
          <input
            type="checkbox"
            checked={showAvailability}
            onChange={(e) => setShowAvailability(e.target.checked)}
          />
          Show availability
        </label>

        <label className="schedule-toggle">
          Seed from template
          <select
            value={selectedTemplateId ?? ''}
            onChange={(e) => setSelectedTemplateId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">None</option>
            {templates.map((t) => (
              <option key={t.template_id} value={t.template_id}>
                {t.name} ({t.entry_count} shifts)
              </option>
            ))}
          </select>
        </label>

        {selectedTemplateId != null && (
          <label className="schedule-toggle">
            Adherence weight ($/shift)
            <input
              type="number"
              min={0}
              max={1000}
              value={templateWeight}
              onChange={(e) => setTemplateWeight(Number(e.target.value))}
              style={{ width: '5rem' }}
            />
          </label>
        )}

        <button onClick={handleGenerate} disabled={generating || loading}>
          {generating ? 'Generating...' : 'Generate schedule'}
        </button>
      </div>

      {generating && (
        <p className="schedule-hint">
          Running the solver for the week of {formatDate(weekStart)} -- this can take up to a couple of minutes.
        </p>
      )}
      {generateError && <p className="form-error">Could not generate a schedule: {generateError}</p>}
      {lockWarning && <p className="warning">{lockWarning}</p>}
      {templateResultNote && <p className="schedule-hint">{templateResultNote}</p>}

      {loading && <p>Loading schedule...</p>}
      {error && <p className="form-error">Failed to load schedule: {error}</p>}

      {schedule && !loading && !error && (
        <>
          <div className="schedule-summary">
            <span>Week total cost: <strong>${schedule.week_total_cost.toLocaleString()}</strong></span>
            <span>Assignments: <strong>{schedule.week_total_assignments}</strong></span>
            <span className={schedule.week_understaffed_shifts > 0 ? 'warning' : ''}>
              Understaffed shifts: <strong>{schedule.week_understaffed_shifts}</strong>
            </span>
            {editSaving && <span className="edited-badge">Saving...</span>}
          </div>
          {editError && <p className="form-error">Could not save that change: {editError}</p>}

          {schedule.week_total_assignments === 0 ? (
            <p className="schedule-empty">
              No schedule has been generated for this week yet. Click <strong>Generate schedule</strong> above to
              run the solver.
            </p>
          ) : (
            <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
              <p className="schedule-hint">
                Drag a shift onto another employee in the same day to reassign it. Click the pencil on a shift to
                edit its time or position.
              </p>
              {showAvailability && (
                <div className="availability-legend">
                  <span className="availability-legend-item">
                    <span className="availability-swatch availability-available" /> Available
                  </span>
                  <span className="availability-legend-item">
                    <span className="availability-swatch availability-unavailable" /> Not available
                  </span>
                  <span className="availability-legend-item">
                    <span className="availability-swatch availability-unknown" /> No availability on file
                  </span>
                </div>
              )}
              <div className="schedule-grid-wrapper">
                <table className="schedule-grid">
                  <thead>
                    <tr>
                      <th className="employee-col">Employee</th>
                      {schedule.week_dates.map((date) => (
                        <th key={date}>
                          {weekdayLabel(date)}
                          <br />
                          {date}
                        </th>
                      ))}
                      <th>Total Hrs</th>
                      <th>Total Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedRows.map((group) => (
                      <Fragment key={group.department}>
                        <tr className="department-row">
                          <td colSpan={columnCount}>
                            {DEPARTMENT_LABELS[group.department] ?? group.department} ({group.employees.length})
                          </td>
                        </tr>
                        {group.employees.map((emp) => (
                          <tr key={emp.employee_id}>
                            <td className="employee-col">{emp.first_name} {emp.last_name}</td>
                            {emp.days.map((day) => (
                              <DroppableCell
                                key={day.date}
                                employeeId={emp.employee_id}
                                date={day.date}
                                {...(showAvailability ? getAvailabilityInfo(emp.employee_id, day.date) : {})}
                              >
                                {day.shifts.map((s) => (
                                  <DraggableShiftChip
                                    key={s.shift_id}
                                    employeeId={emp.employee_id}
                                    date={day.date}
                                    shift={s}
                                    roles={roles}
                                    onRemove={() => handleRemoveShift(emp.employee_id, day.date, s.shift_id)}
                                    onEdit={(edit) => handleEditShift(emp.employee_id, day.date, s.shift_id, edit)}
                                  />
                                ))}
                              </DroppableCell>
                            ))}
                            <td>{emp.total_hours}</td>
                            <td>${emp.total_cost.toLocaleString()}</td>
                          </tr>
                        ))}
                      </Fragment>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td className="employee-col">Daily totals</td>
                      {schedule.daily_totals.map((d) => (
                        <td key={d.date}>
                          {d.headcount} people
                          <br />
                          ${d.cost.toLocaleString()}
                          {d.understaffed_shifts > 0 && (
                            <div className="warning">{d.understaffed_shifts} short</div>
                          )}
                        </td>
                      ))}
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                </table>
              </div>

              <DragOverlay>{activeShift && <ShiftChipPreview shift={activeShift} />}</DragOverlay>
            </DndContext>
          )}
        </>
      )}
    </div>
  )
}

export default Schedule
