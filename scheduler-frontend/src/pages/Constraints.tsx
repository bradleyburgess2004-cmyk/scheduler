import { useEffect, useMemo, useState } from 'react'
import {
  getConstraints,
  getRestaurantConstraints,
  createRestaurantConstraint,
  updateRestaurantConstraint,
  deleteRestaurantConstraint,
  getRoles,
  getEmployees,
  type ConstraintCatalogItem,
  type RestaurantConstraint,
  type Role,
  type Employee,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { onConstraintApplied } from '../aiConstraintEvents'
import { NOT_YET_IMPLEMENTED } from '../constraintHints'
import { SOFT_WITH_PRIORITY, PRIORITY_PRESETS, priorityLevelForWeight } from '../constraintPriority'
import ParameterField from '../components/ParameterField'
import PositionStaffingManager from '../components/PositionStaffingManager'
import './Constraints.css'

interface RowState {
  key: string // stable client-side key -- unsaved rows have no config_id yet
  configId: number | null
  enabled: boolean
  weightText: string // empty string = hard constraint (weight = null)
  values: Record<string, unknown>
  saving: boolean
  saveError: string | null
  saved: boolean
}

let nextTempKey = 0

function emptyRow(isSoftWithPriority: boolean): RowState {
  nextTempKey += 1
  return {
    key: `new-${nextTempKey}`,
    configId: null,
    enabled: false,
    weightText: isSoftWithPriority ? String(PRIORITY_PRESETS.medium) : '',
    values: {},
    saving: false,
    saveError: null,
    saved: false,
  }
}

function rowFromExisting(existing: RestaurantConstraint): RowState {
  return {
    key: String(existing.config_id),
    configId: existing.config_id,
    enabled: existing.enabled ?? false,
    weightText: existing.weight != null ? String(existing.weight) : '',
    values: existing.parameter_json ? { ...existing.parameter_json } : {},
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

function summarizeParams(
  catalogItem: ConstraintCatalogItem | undefined,
  params: Record<string, unknown> | null,
  employees: Employee[],
): string {
  const fields = catalogItem?.parameter_spec || []
  if (!params || fields.length === 0) return '—'
  const parts: string[] = []
  for (const f of fields) {
    const v = params[f.key]
    if (isEmpty(v)) continue
    let display: string
    switch (f.type) {
      case 'employee': {
        const emp = employees.find((e) => e.employee_id === v)
        display = emp ? `${emp.first_name} ${emp.last_name}` : `#${v}`
        break
      }
      case 'day_multi':
        display = Array.isArray(v) ? v.join(', ') : String(v)
        break
      case 'employee_pairs':
        display = Array.isArray(v) ? `${v.length} pair(s)` : '—'
        break
      case 'requirement_list':
        display = Array.isArray(v) ? `${v.length} requirement(s)` : '—'
        break
      case 'boolean':
        display = v ? 'Yes' : 'No'
        break
      default:
        display = String(v)
    }
    parts.push(`${f.label}: ${display}`)
  }
  return parts.length ? parts.join(' · ') : '—'
}

function Constraints() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()

  const [catalog, setCatalog] = useState<ConstraintCatalogItem[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [rows, setRows] = useState<Record<number, RowState[]>>({})
  const [configured, setConfigured] = useState<RestaurantConstraint[]>([])
  const [positionStaffingRefreshKey, setPositionStaffingRefreshKey] = useState(0)
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
        setConfigured(mine)
        const rowsByConstraintId = new Map<number, RestaurantConstraint[]>()
        mine.forEach((rc) => {
          const list = rowsByConstraintId.get(rc.constraint_id) ?? []
          list.push(rc)
          rowsByConstraintId.set(rc.constraint_id, list)
        })

        const initialRows: Record<number, RowState[]> = {}
        constraints.forEach((c) => {
          const isSoft = !!c.class_name && SOFT_WITH_PRIORITY.has(c.class_name)
          const existingRows = rowsByConstraintId.get(c.constraint_id) ?? []
          initialRows[c.constraint_id] = existingRows.length > 0
            ? existingRows.map(rowFromExisting)
            : [emptyRow(isSoft)]
        })
        setRows(initialRows)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [restaurant])

  function reloadConfigured() {
    if (!restaurant) return
    getRestaurantConstraints()
      .then((all) => setConfigured(all.filter((rc) => rc.restaurant_id === restaurant.restaurant_id)))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }

  // The floating AI chat widget (visible on every page, including this
  // one) can write a restaurant_constraints row -- or a
  // MinPositionStaffingConstraint row -- at any time. Pick that up
  // without requiring a manual page refresh.
  useEffect(() => {
    return onConstraintApplied(() => {
      reloadConfigured()
      setPositionStaffingRefreshKey((k) => k + 1)
    })
  }, [restaurant])

  const catalogById = useMemo(() => new Map(catalog.map((c) => [c.constraint_id, c])), [catalog])

  function addRow(constraintId: number) {
    const catalogItem = catalogById.get(constraintId)
    const isSoft = !!catalogItem?.class_name && SOFT_WITH_PRIORITY.has(catalogItem.class_name)
    setRows((prev) => ({
      ...prev,
      [constraintId]: [...(prev[constraintId] ?? []), emptyRow(isSoft)],
    }))
  }

  async function handleDelete(configId: number, constraintId: number) {
    setRows((prev) => ({
      ...prev,
      [constraintId]: (prev[constraintId] ?? []).map((r) =>
        r.configId === configId ? { ...r, saving: true, saveError: null } : r
      ),
    }))
    try {
      await deleteRestaurantConstraint(configId)
      setConfigured((prev) => prev.filter((rc) => rc.config_id !== configId))
      const catalogItem = catalogById.get(constraintId)
      if (catalogItem?.class_name === 'MinPositionStaffingConstraint') {
        setPositionStaffingRefreshKey((k) => k + 1)
        return
      }
      setRows((prev) => {
        const remaining = (prev[constraintId] ?? []).filter((r) => r.configId !== configId)
        const isSoft = !!catalogItem?.class_name && SOFT_WITH_PRIORITY.has(catalogItem.class_name)
        return {
          ...prev,
          [constraintId]: remaining.length > 0 ? remaining : [emptyRow(isSoft)],
        }
      })
    } catch (err) {
      setRows((prev) => ({
        ...prev,
        [constraintId]: (prev[constraintId] ?? []).map((r) =>
          r.configId === configId
            ? { ...r, saving: false, saveError: err instanceof Error ? err.message : String(err) }
            : r
        ),
      }))
    }
  }

  // Removes a not-yet-saved row added via "+ Add rule" -- purely local
  // state, no API call, since there's nothing in the database to delete.
  function removeDraftRow(constraintId: number, key: string) {
    const catalogItem = catalogById.get(constraintId)
    const isSoft = !!catalogItem?.class_name && SOFT_WITH_PRIORITY.has(catalogItem.class_name)
    setRows((prev) => {
      const remaining = (prev[constraintId] ?? []).filter((r) => r.key !== key)
      return {
        ...prev,
        [constraintId]: remaining.length > 0 ? remaining : [emptyRow(isSoft)],
      }
    })
  }

  const visibleCatalog = useMemo(() => {
    // MinPositionStaffingConstraint gets its own dedicated section below --
    // its per-position requirement list is a different shape from the
    // simple repeatable-row pattern the rest use.
    const withoutPositionStaffing = catalog.filter((c) => c.class_name !== 'MinPositionStaffingConstraint')
    if (!search.trim()) return withoutPositionStaffing
    const term = search.trim().toLowerCase()
    return withoutPositionStaffing.filter((c) => c.name.toLowerCase().includes(term))
  }, [catalog, search])

  function updateRow(constraintId: number, key: string, patch: Partial<RowState>) {
    setRows((prev) => ({
      ...prev,
      [constraintId]: (prev[constraintId] ?? []).map((r) => (r.key === key ? { ...r, ...patch } : r)),
    }))
  }

  function updateFieldValue(constraintId: number, key: string, fieldKey: string, fieldValue: unknown) {
    setRows((prev) => ({
      ...prev,
      [constraintId]: (prev[constraintId] ?? []).map((r) =>
        r.key === key
          ? { ...r, values: { ...r.values, [fieldKey]: fieldValue }, saved: false, saveError: null }
          : r
      ),
    }))
  }

  async function handleSave(constraint: ConstraintCatalogItem, key: string) {
    if (!restaurant) return
    const row = (rows[constraint.constraint_id] ?? []).find((r) => r.key === key)
    if (!row) return
    const fields = constraint.parameter_spec || []

    const missing = fields.filter((f) => !f.optional && isEmpty(row.values[f.key]))
    if (missing.length > 0) {
      updateRow(constraint.constraint_id, key, {
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

    updateRow(constraint.constraint_id, key, { saving: true, saved: false, saveError: null })

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
        updateRow(constraint.constraint_id, key, { saving: false, saved: true })
      } else {
        const created = await createRestaurantConstraint(input)
        updateRow(constraint.constraint_id, key, {
          saving: false,
          saved: true,
          configId: created.config_id,
          key: String(created.config_id),
        })
      }
      reloadConfigured()
    } catch (err) {
      updateRow(constraint.constraint_id, key, {
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
        (a cost penalty the solver weighs against labor cost). Any rule can be added more than
        once -- e.g. one row per employee, per day, or per role -- with "+ Add rule".
      </p>

      {!loading && !error && (
        <div className="configured-overview">
          <h2>Currently configured ({configured.length})</h2>
          {configured.length === 0 ? (
            <p className="no-params">No rules configured yet — set one up below.</p>
          ) : (
            <table className="configured-table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Summary</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {configured.map((rc) => {
                  const catalogItem = catalogById.get(rc.constraint_id)
                  const row = (rows[rc.constraint_id] ?? []).find((r) => r.configId === rc.config_id)
                  return (
                    <tr key={rc.config_id}>
                      <td>{catalogItem?.name ?? `Constraint #${rc.constraint_id}`}</td>
                      <td>{rc.weight == null ? 'Hard' : 'Soft'}</td>
                      <td>
                        <span className={rc.enabled ? 'badge badge-enabled' : 'badge badge-disabled'}>
                          {rc.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </td>
                      <td>{summarizeParams(catalogItem, rc.parameter_json, employees)}</td>
                      <td>
                        <button
                          type="button"
                          className="danger-link"
                          disabled={row?.saving}
                          onClick={() => handleDelete(rc.config_id, rc.constraint_id)}
                        >
                          {row?.saving ? 'Removing...' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!loading && !error && (
        <>
          <PositionStaffingManager key={positionStaffingRefreshKey} onChange={reloadConfigured} />
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
            const ruleRows = rows[constraint.constraint_id] ?? []
            const notImplemented = constraint.class_name ? NOT_YET_IMPLEMENTED.has(constraint.class_name) : false
            const fields = constraint.parameter_spec || []
            const isSoft = !!constraint.class_name && SOFT_WITH_PRIORITY.has(constraint.class_name)

            return (
              <div key={constraint.constraint_id} className="constraint-group">
                <div className="constraint-group-header">
                  <span className="constraint-name">{constraint.name}</span>
                  {notImplemented && (
                    <span className="badge badge-warning">not yet implemented in the solver</span>
                  )}
                </div>
                <p className="constraint-description">{constraint.description}</p>

                {ruleRows.map((row, index) => (
                  <div key={row.key} className="constraint-card">
                    {ruleRows.length > 1 && (
                      <p className="constraint-rule-index">Rule {index + 1} of {ruleRows.length}</p>
                    )}
                    <div className="constraint-header">
                      <label className="constraint-enabled">
                        <input
                          type="checkbox"
                          checked={row.enabled}
                          onChange={(e) =>
                            updateRow(constraint.constraint_id, row.key, {
                              enabled: e.target.checked,
                              saved: false,
                              saveError: null,
                            })
                          }
                        />
                        <span className="constraint-name">Enabled</span>
                      </label>
                    </div>

                    <div className="constraint-fields">
                      {isSoft ? (
                        <label className="weight-field">
                          Priority
                          <select
                            value={priorityLevelForWeight(row.weightText.trim() ? Number(row.weightText) : null)}
                            onChange={(e) =>
                              updateRow(constraint.constraint_id, row.key, {
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
                              onChange={(v) => updateFieldValue(constraint.constraint_id, row.key, f.key, v)}
                              roles={roles}
                              employees={employees}
                            />
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="constraint-actions">
                      <button onClick={() => handleSave(constraint, row.key)} disabled={row.saving}>
                        {row.saving ? 'Saving...' : 'Save'}
                      </button>
                      {row.configId !== null ? (
                        <button
                          type="button"
                          className="danger-link"
                          disabled={row.saving}
                          onClick={() => handleDelete(row.configId as number, constraint.constraint_id)}
                        >
                          Delete
                        </button>
                      ) : (
                        ruleRows.length > 1 && (
                          <button
                            type="button"
                            className="danger-link"
                            onClick={() => removeDraftRow(constraint.constraint_id, row.key)}
                          >
                            Remove
                          </button>
                        )
                      )}
                      {row.saved && <span className="saved-indicator">Saved</span>}
                      {row.saveError && <span className="error-indicator">{row.saveError}</span>}
                    </div>
                  </div>
                ))}

                {constraint.supports_multiple && (
                  <button
                    type="button"
                    className="add-rule-button"
                    onClick={() => addRow(constraint.constraint_id)}
                  >
                    + Add rule
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default Constraints
