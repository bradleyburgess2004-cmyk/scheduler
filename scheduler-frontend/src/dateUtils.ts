/** Format as YYYY-MM-DD using local date parts -- avoids the
 * off-by-one-day bug from Date.toISOString(), which converts to UTC
 * first. */
export function formatDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function addDays(date: Date, days: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result
}

/** Monday of the week containing `date` (Date.getDay() is 0=Sun..6=Sat). */
export function mondayOfWeek(date: Date): Date {
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day
  return addDays(date, diff)
}

export function parseLocalDate(isoDate: string): Date {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d)
}

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export function weekdayLabel(isoDate: string): string {
  return WEEKDAY_LABELS[parseLocalDate(isoDate).getDay()]
}

/** Mirrors the backend's shift_hours() (app/optimizer/time_utils.py) --
 * treats end <= start as an overnight shift wrapping past midnight.
 * Accepts "HH:MM" or "HH:MM:SS". */
export function shiftHours(startTime: string, endTime: string): number {
  const [startH, startM] = startTime.split(':').map(Number)
  const [endH, endM] = endTime.split(':').map(Number)
  const startMinutes = startH * 60 + startM
  let endMinutes = endH * 60 + endM
  if (endMinutes <= startMinutes) endMinutes += 24 * 60
  return (endMinutes - startMinutes) / 60
}
