import { useEffect, useMemo, useState } from 'react'
import {
  getConstraints,
  getRestaurantConstraints,
  createRestaurantConstraint,
  updateRestaurantConstraint,
  getRoles,
  getEmployees,
  type ConstraintCatalogItem,
  type RestaurantConstraint,
  type Role,
  type Employee,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { NOT_YET_IMPLEMENTED } from '../constraintHints'
import { SOFT_WITH_PRIORITY, PRIORITY_PRESETS, priorityLevelForWeight } from '../constraintPriority'
import ParameterField from '../components/ParameterField'
import PositionStaffingManager from '../components/PositionStaffingManager'
import './Constraints.css'

interface RowState {
  configId: number | null
  enabled: boolean
  weightText: string // empty string = hard constraint (weight = null)
  values: Record<string, unknown>
  saving: boolean
  saveError: string | null
  saved: boolean
}

function initialRowState(existing: RestaurantConstraint | undefined, isSoftWithPriority: boolean): RowState {
  const defaultWeightText = existing?.weight != null
    ? String(existing.weight)
    : isSoftWithPriority
      ? String(PRIORITY_PRESETS.medium)
      : ''
  return {
    configId: existing?.config_id ?? null,
    enabled: existing?.enabled ?? false,
    weightText: defaultWeightText,
    values: existing?.parameter_json ? { ...existing.parameter_json } : {},
    saving: false,
    saveError: null,
    saved: false,
  }
}

function isEmpty(value: unknown): boolean {
  if (value == null) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  return false
}

function Constraints() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()

  const [catalog, setCatalog] = useState<ConstraintCatalogItem[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [rows, setRows] = useState<Record<number, RowState>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!restaurant) return
    setLoading(true)
    setError(null)
    Promise.all([getConstraints(), getRestaurantConstraints(), getRoles(), getEmployees()])
      .then(([constraints, restaurantConstraints, roleList, employeeList]) => {
        setCatalog(constraints)
        setRoles([...roleList].sort((a, b) => a.role_name.localeCompare(b.role_name)))
        setEmployees(
          [...employeeList].sort((a, b) =>
            `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`)
          )
        )

        const mine = restaurantConstraints.filter((rc) => rc.restaurant_id === restaurant.restaurant_id)
        const byConstraintId = new Map(mine.map((rc) => [rc.constraint_id, rc]))

        const initialRows: Record<number, RowState> = {}
        constraints.forEach((c) => {
          const isSoft = !!c.class_name && SOFT_WITH_PRIORITY.has(c.class_name)
          initialRows[c.constraint_id] = initialRowState(byConstraintId.get(c.constraint_id), isSoft)
        })
        setRows(initialRows)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [restaurant])

  const visibleCatalog = useMemo(() => {
    // MinPositionStaffingConstraint gets its own dedicated section below --
    // it supports multiple named rules per restaurant, which doesn't fit
    // the single-enabled/single-weight card pattern the rest use.
    const withoutPositionStaffing = catalog.filter((c) => c.class_name !== 'MinPositionStaffingConstraint')
    if (!search.trim()) return withoutPositionStaffing
    const term = search.trim().toLowerCase()
    return withoutPositionStaffing.filter((c) => c.name.toLowerCase().includes(term))
  }, [catalog, search])

  function updateRow(constraintId: number, patch: Partial<RowState>) {
    setRows((prev) => ({
      ...prev,
      [constraintId]: { ...prev[constraintId], ...patch },
    }))
  }

  function updateFieldValue(constraintId: number, key: string, fieldValue: unknown) {
    setRows((prev) => ({
      ...prev,
      [constraintId]: {
        ...prev[constraintId],
        values: { ...prev[constraintId].values, [key]: fieldValue },
        saved: false,
        saveError: null,
      },
    }))
  }

  async function handleSave(constraint: ConstraintCatalogItem) {
    if (!restaurant) return
    const row = rows[constraint.constraint_id]
    const fields = constraint.parameter_spec || []

    const missing = fields.filter((f) => !f.optional && isEmpty(row.values[f.key]))
    if (missing.length > 0) {
      updateRow(constraint.constraint_id, {
        saved: false,
        saveError: `Please fill in: ${missing.map((f) => f.label).join(', ')}`,
      })
      return
    }

    const parameterJson: Record<string, unknown> = {}
    fields.forEach((f) => {
      let value = row.values[f.key]
      if (f.type === 'employee_pairs' && Array.isArray(value)) {
        value = (value as (number | null)[][]).filter((pair) => pair[0] != null && pair[1] != null)
      }
      if (!isEmpty(value)) {
        parameterJson[f.key] = value
      }
    })

    updateRow(constraint.constraint_id, { saving: true, saved: false, saveError: null })

    const input = {
      restaurant_id: restaurant.restaurant_id,
      constraint_id: constraint.constraint_id,
      enabled: row.enabled,
      weight: row.weightText.trim() ? Number(row.weightText) : null,
      parameter_json: parameterJson,
    }

    try {
      if (row.configId !== null) {
        await updateRestaurantConstraint(row.configId, input)
        updateRow(constraint.constraint_id, { saving: false, saved: true })
      } else {
        const created = await createRestaurantConstraint(input)
        updateRow(constraint.constraint_id, { saving: false, saved: true, configId: created.config_id })
      }
    } catch (err) {
      updateRow(constraint.constraint_id, {
        saving: false,
        saveError: err instanceof Error ? err.message : String(err),
      })
    }
  }

  if (restaurantLoading) return <p>Loading...</p>
  if (restaurantError) return <p className="form-error">{restaurantError}</p>

  return (
    <div>
      <h1>Constraints</h1>
      <p className="constraints-intro">
        Configure which of the {catalog.length} scheduling rules apply, and their parameters.
        Only rules marked <strong>enabled</strong> are used the next time the solver runs.
        Leave weight blank for a hard rule (never violated); set a number for a soft rule
        (a cost penalty the solver weighs against labor cost).
      </p>

      {!loading && !error && (
        <>
          <PositionStaffingManager />
          <hr className="constraints-section-divider" />
        </>
      )}

      <input
        type="text"
        placeholder="Search constraints..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="constraints-search"
      />

      {loading && <p>Loading constraints...</p>}
      {error && <p className="form-error">Failed to load constraints: {error}</p>}

      {!loading && !error && (
        <div className="constraint-list">
          {visibleCatalog.map((constraint) => {
            const row = rows[constraint.constraint_id]
            if (!row) return null
            const notImplemented = constraint.class_name ? NOT_YET_IMPLEMENTED.has(constraint.class_name) : false
            const fields = constraint.parameter_spec || []

            return (
              <div key={constraint.constraint_id} className="constraint-card">
                <div className="constraint-header">
                  <label className="constraint-enabled">
                    <input
                      type="checkbox"
                      checked={row.enabled}
                      onChange={(e) =>
                        updateRow(constraint.constraint_id, {
                          enabled: e.target.checked,
                          saved: false,
                          saveError: null,
                        })
                      }
                    />
                    <span className="constraint-name">{constraint.name}</span>
                  </label>
                  {notImplemented && (
                    <span className="badge badge-warning">not yet implemented in the solver</span>
                  )}
                </div>

                <p className="constraint-description">{constraint.description}</p>

                <div className="constraint-fields">
                  {constraint.class_name && SOFT_WITH_PRIORITY.has(constraint.class_name) ? (
                    <label className="weight-field">
                      Priority
                      <select
                        value={priorityLevelForWeight(row.weightText.trim() ? Number(row.weightText) : null)}
                        onChange={(e) =>
                          updateRow(constraint.constraint_id, {
                            weightText: String(PRIORITY_PRESETS[e.target.value as keyof typeof PRIORITY_PRESETS]),
                            saved: false,
                            saveError: null,
                          })
                        }
                      >
                        <option value="low">Low priority</option>
                        <option value="medium">Medium priority</option>
                        <option value="high">High priority</option>
                        {priorityLevelForWeight(row.weightText.trim() ? Number(row.weightText) : null) === 'custom' && (
                          <option value="custom" disabled>
                            Custom ({row.weightText || 'unset'})
                          </option>
                        )}
                      </select>
                    </label>
                  ) : (
                    <p className="always-enforced">Always enforced when enabled.</p>
                  )}

                  {fields.length === 0 ? (
                    <p className="no-params">No parameters needed for this rule.</p>
                  ) : (
                    <div className="param-fields">
                      {fields.map((f) => (
                        <ParameterField
                          key={f.key}
                          spec={f}
                          value={row.values[f.key]}
                          onChange={(v) => updateFieldValue(constraint.constraint_id, f.key, v)}
                          roles={roles}
                          employees={employees}
                        />
                      ))}
                    </div>
                  )}
                </div>

                <div className="constraint-actions">
                  <button onClick={() => handleSave(constraint)} disabled={row.saving}>
                    {row.saving ? 'Saving...' : 'Save'}
                  </button>
                  {row.saved && <span className="saved-indicator">Saved</span>}
                  {row.saveError && <span className="error-indicator">{row.saveError}</span>}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default Constraints
