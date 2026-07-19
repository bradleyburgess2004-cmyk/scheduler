import type { ScheduleResponse, EmployeeScheduleRow } from './api'

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

/** Recomputes every derived number (per-employee hours/cost, per-shift
 * understaffed flags, daily and week totals) from the current
 * employees/days/shifts state. Called after every local drag or
 * remove edit -- cheap at this data size, and far less error-prone
 * than patching each affected total incrementally. */
export function recomputeSchedule(schedule: ScheduleResponse): ScheduleResponse {
  const countByShiftId = new Map<number, number>()
  const requiredByShiftId = new Map<number, number>()
  for (const emp of schedule.employees) {
    for (const day of emp.days) {
      for (const s of day.shifts) {
        countByShiftId.set(s.shift_id, (countByShiftId.get(s.shift_id) ?? 0) + 1)
        requiredByShiftId.set(s.shift_id, s.required_employees)
      }
    }
  }

  function isUnderstaffed(shiftId: number): boolean {
    const count = countByShiftId.get(shiftId) ?? 0
    const required = requiredByShiftId.get(shiftId) ?? 1
    return count < required
  }

  const employees: EmployeeScheduleRow[] = schedule.employees.map((emp) => {
    let totalHours = 0
    const days = emp.days.map((day) => {
      const shifts = day.shifts.map((s) => {
        totalHours += s.hours
        return { ...s, understaffed: isUnderstaffed(s.shift_id) }
      })
      return { ...day, shifts }
    })
    return {
      ...emp,
      total_hours: round2(totalHours),
      total_cost: round2(totalHours * emp.hourly_rate),
      days,
    }
  })

  const dailyTotals = schedule.week_dates.map((date) => {
    let headcount = 0
    let cost = 0
    const understaffedShiftIdsThisDay = new Set<number>()
    for (const emp of employees) {
      const day = emp.days.find((d) => d.date === date)
      if (!day) continue
      for (const s of day.shifts) {
        headcount += 1
        cost += s.hours * emp.hourly_rate
        if (s.understaffed) understaffedShiftIdsThisDay.add(s.shift_id)
      }
    }
    return { date, headcount, cost: round2(cost), understaffed_shifts: understaffedShiftIdsThisDay.size }
  })

  const weekTotalCost = round2(employees.reduce((sum, e) => sum + e.total_cost, 0))
  const weekTotalAssignments = employees.reduce(
    (sum, e) => sum + e.days.reduce((daySum, d) => daySum + d.shifts.length, 0),
    0
  )
  const understaffedShiftIdsWeek = new Set<number>()
  for (const emp of employees) {
    for (const day of emp.days) {
      for (const s of day.shifts) {
        if (s.understaffed) understaffedShiftIdsWeek.add(s.shift_id)
      }
    }
  }

  return {
    ...schedule,
    employees,
    daily_totals: dailyTotals,
    week_total_cost: weekTotalCost,
    week_total_assignments: weekTotalAssignments,
    week_understaffed_shifts: understaffedShiftIdsWeek.size,
  }
}
