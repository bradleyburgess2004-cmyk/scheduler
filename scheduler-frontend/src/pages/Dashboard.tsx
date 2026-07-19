import { useEffect, useMemo, useState } from 'react'
import { getLaborAnalytics, type LaborAnalyticsResponse } from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { formatDate, mondayOfWeek } from '../dateUtils'
import { DEPARTMENT_LABELS } from '../departments'
import './Dashboard.css'

function currency(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function Dashboard() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()
  const [analytics, setAnalytics] = useState<LaborAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const thisWeekStart = useMemo(() => formatDate(mondayOfWeek(new Date())), [])

  useEffect(() => {
    if (!restaurant) return
    setLoading(true)
    setError(null)
    getLaborAnalytics(restaurant.restaurant_id, { weeks: 8, weekStart: thisWeekStart })
      .then(setAnalytics)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [restaurant, thisWeekStart])

  if (restaurantLoading) return <p>Loading...</p>
  if (restaurantError) return <p className="form-error">{restaurantError}</p>

  const thisWeek = analytics?.weekly_trend.find((w) => w.week_start === thisWeekStart) ?? null
  const maxCost = analytics ? Math.max(1, ...analytics.weekly_trend.map((w) => w.total_cost)) : 1
  const maxDeptCost = analytics ? Math.max(1, ...analytics.department_breakdown.map((d) => d.cost)) : 1

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="dashboard-subtitle">
        {restaurant?.name}{restaurant?.location ? ` — ${restaurant.location}` : ''}
      </p>

      {loading && <p>Loading labor data...</p>}
      {error && <p className="form-error">Failed to load labor data: {error}</p>}

      {!loading && !error && analytics && (
        <>
          <section className="dashboard-section">
            <h2>This week</h2>
            {thisWeek ? (
              <div className="stat-cards">
                <div className="stat-card">
                  <span className="stat-label">Labor cost</span>
                  <span className="stat-value">{currency(thisWeek.total_cost)}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Shifts filled</span>
                  <span className="stat-value">
                    {thisWeek.total_assignments} <span className="stat-value-sub">assignments</span>
                  </span>
                </div>
                <div className={`stat-card ${thisWeek.understaffed_shifts > 0 ? 'stat-card-warning' : ''}`}>
                  <span className="stat-label">Understaffed shifts</span>
                  <span className="stat-value">{thisWeek.understaffed_shifts}</span>
                </div>
              </div>
            ) : (
              <p className="dashboard-empty">
                No schedule has been generated for the week of {thisWeekStart} yet. Run the solver, then check
                back here.
              </p>
            )}
          </section>

          <section className="dashboard-section">
            <h2>Labor cost trend</h2>
            {analytics.weekly_trend.length === 0 ? (
              <p className="dashboard-empty">No shifts have been scheduled yet.</p>
            ) : (
              <div className="trend-chart">
                {analytics.weekly_trend.map((w) => (
                  <div key={w.week_start} className="trend-bar-col">
                    <span className="trend-bar-value">{currency(w.total_cost)}</span>
                    <div className="trend-bar-track">
                      <div
                        className={`trend-bar ${w.understaffed_shifts > 0 ? 'trend-bar-warning' : ''}`}
                        style={{ height: `${Math.max(4, (w.total_cost / maxCost) * 100)}%` }}
                        title={`${w.total_assignments} assignments, ${w.understaffed_shifts} understaffed`}
                      />
                    </div>
                    <span className="trend-bar-label">{w.week_start}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="dashboard-section">
            <h2>Cost by department {analytics.breakdown_week_start ? `(week of ${analytics.breakdown_week_start})` : ''}</h2>
            {analytics.department_breakdown.length === 0 ? (
              <p className="dashboard-empty">No scheduled shifts for that week yet.</p>
            ) : (
              <div className="department-bars">
                {analytics.department_breakdown.map((d) => (
                  <div key={d.department} className="department-bar-row">
                    <span className="department-bar-label">{DEPARTMENT_LABELS[d.department] ?? d.department}</span>
                    <div className="department-bar-track">
                      <div className="department-bar" style={{ width: `${Math.max(2, (d.cost / maxDeptCost) * 100)}%` }} />
                    </div>
                    <span className="department-bar-value">{currency(d.cost)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}

export default Dashboard
