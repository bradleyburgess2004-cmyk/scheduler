import { useEffect, useState } from 'react'
import {
  getConstraints,
  getRestaurantConstraints,
  createRestaurantConstraint,
  updateRestaurantConstraint,
  deleteRestaurantConstraint,
  getRoles,
  type Role,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { DEPARTMENT_ORDER } from '../departments'
import { DAY_OPTIONS } from '../constraintFormSpecs'

interface RequirementRow {
  days: string[]
  start_time: string
  end_time: string
  min_count: number | null
}

interface RuleState {
  key: string // stable client-side key -- unsaved rules have no config_id yet
  configId: number | null
  enabled: boolean
  positionType: 'role' | 'department'
  positionValue: string
  requirements: RequirementRow[]
  saving: boolean
  deleting: boolean
  saveError: string | null
  saved: boolean
}

function emptyRequirement(): RequirementRow {
  return { days: [], start_time: '', end_time: '', min_count: null }
}

function emptyRule(key: string): RuleState {
  return {
    key,
    configId: null,
    enabled: true,
    positionType: 'department',
    positionValue: '',
    requirements: [emptyRequirement()],
    saving: false,
    deleting: false,
    saveError: null,
    saved: false,
  }
}

function ruleFromRow(configId: number, enabled: boolean, params: Record<string, unknown>): RuleState {
  const rawRequirements = Array.isArray(params.requirements) ? params.requirements : []
  const requirements = rawRequirements.map((r) => {
    const req = r as Record<string, unknown>
    const days = Array.isArray(req.days)
      ? req.days.filter((d): d is string => typeof d === 'string')
      : typeof req.day === 'string' && req.day
        ? [req.day]
        : []
    return {
      days,
      start_time: typeof req.start_time === 'string' ? req.start_time : '',
      end_time: typeof req.end_time === 'string' ? req.end_time : '',
      min_count: typeof req.min_count === 'number' ? req.min_count : null,
    }
  })
  return {
    key: String(configId),
    configId,
    enabled,
    positionType: params.position_type === 'role' ? 'role' : 'department',
    positionValue: typeof params.position_value === 'string' ? params.position_value : '',
    requirements: requirements.length ? requirements : [emptyRequirement()],
    saving: false,
    deleting: false,
    saveError: null,
    saved: false,
  }
}

let nextTempKey = 0

function PositionStaffingManager() {
  const { restaurant } = useCurrentRestaurant()
  const [constraintId, setConstraintId] = useState<number | null>(null)
  const [roles, setRoles] = useState<Role[]>([])
  const [rules, setRules] = useState<RuleState[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!restaurant) return
    setLoading(true)
    setError(null)
    Promise.all([getConstraints(), getRestaurantConstraints(), getRoles()])
      .then(([catalog, restaurantConstraints, roleList]) => {
        const catalogItem = catalog.find((c) => c.class_name === 'MinPositionStaffingConstraint')
        if (!catalogItem) {
          setError('Min Position Staffing constraint is not registered in the catalog.')
          return
        }
        setConstraintId(catalogItem.constraint_id)
        setRoles([...roleList].sort((a, b) => a.role_name.localeCompare(b.role_name)))

        const mine = restaurantConstraints.filter(
          (rc) => rc.restaurant_id === restaurant.restaurant_id && rc.constraint_id === catalogItem.constraint_id
        )
        setRules(mine.map((rc) => ruleFromRow(rc.config_id, rc.enabled ?? false, rc.parameter_json ?? {})))
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [restaurant])

  function patchRule(key: string, patch: Partial<RuleState>) {
    setRules((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch, saved: false, saveError: null } : r)))
  }

  function updateRequirement(key: string, index: number, patch: Partial<RequirementRow>) {
    setRules((prev) =>
      prev.map((r) => {
        if (r.key !== key) return r
        const requirements = r.requirements.map((req, i) => (i === index ? { ...req, ...patch } : req))
        return { ...r, requirements, saved: false, saveError: null }
      })
    )
  }

  function addRequirement(key: string) {
    setRules((prev) =>
      prev.map((r) =>
        r.key === key
          ? { ...r, requirements: [...r.requirements, emptyRequirement()], saved: false, saveError: null }
          : r
      )
    )
  }

  function removeRequirement(key: string, index: number) {
    setRules((prev) =>
      prev.map((r) => {
        if (r.key !== key) return r
        const requirements = r.requirements.filter((_, i) => i !== index)
        return { ...r, requirements: requirements.length ? requirements : [emptyRequirement()], saved: false, saveError: null }
      })
    )
  }

  function addRule() {
    nextTempKey += 1
    setRules((prev) => [...prev, emptyRule(`new-${nextTempKey}`)])
  }

  async function handleSave(key: string) {
    if (!restaurant || constraintId == null) return
    const rule = rules.find((r) => r.key === key)
    if (!rule) return

    if (!rule.positionValue) {
      patchRule(key, { saveError: `Please select a ${rule.positionType === 'role' ? 'role' : 'department'}.` })
      return
    }
    const cleanedRequirements = rule.requirements.filter(
      (r) => r.days.length > 0 && r.start_time && r.end_time && r.min_count != null
    )
    if (cleanedRequirements.length === 0) {
      patchRule(key, { saveError: 'Add at least one complete day / time / minimum requirement.' })
      return
    }

    setRules((prev) => prev.map((r) => (r.key === key ? { ...r, saving: true, saveError: null, saved: false } : r)))

    const input = {
      restaurant_id: restaurant.restaurant_id,
      constraint_id: constraintId,
      enabled: rule.enabled,
      weight: null,
      parameter_json: {
        position_type: rule.positionType,
        position_value: rule.positionValue,
        requirements: cleanedRequirements,
      },
    }

    try {
      if (rule.configId !== null) {
        await updateRestaurantConstraint(rule.configId, input)
        setRules((prev) => prev.map((r) => (r.key === key ? { ...r, saving: false, saved: true } : r)))
      } else {
        const created = await createRestaurantConstraint(input)
        setRules((prev) =>
          prev.map((r) =>
            r.key === key
              ? { ...r, saving: false, saved: true, configId: created.config_id, key: String(created.config_id) }
              : r
          )
        )
      }
    } catch (err) {
      setRules((prev) =>
        prev.map((r) =>
          r.key === key ? { ...r, saving: false, saveError: err instanceof Error ? err.message : String(err) } : r
        )
      )
    }
  }

  async function handleDelete(key: string) {
    const rule = rules.find((r) => r.key === key)
    if (!rule) return
    if (rule.configId === null) {
      setRules((prev) => prev.filter((r) => r.key !== key))
      return
    }
    setRules((prev) => prev.map((r) => (r.key === key ? { ...r, deleting: true } : r)))
    try {
      await deleteRestaurantConstraint(rule.configId)
      setRules((prev) => prev.filter((r) => r.key !== key))
    } catch (err) {
      setRules((prev) =>
        prev.map((r) =>
          r.key === key ? { ...r, deleting: false, saveError: err instanceof Error ? err.message : String(err) } : r
        )
      )
    }
  }

  if (loading) return <p>Loading position staffing rules...</p>
  if (error) return <p className="form-error">{error}</p>

  return (
    <div className="position-staffing">
      <h2>Minimum Position Staffing</h2>
      <p className="constraints-intro">
        Require a minimum headcount for a role or department during specific day/time windows —
        e.g. at least 5 people in Back of House on Saturday from 5:00 AM to 11:00 AM. Add one rule
        per position; each rule can cover several day/time slots. If a window can never be fully
        covered by existing shifts, the solver fills it as much as possible rather than failing to
        build a schedule.
      </p>

      <div className="position-rule-list">
        {rules.map((rule) => (
          <div key={rule.key} className="constraint-card position-rule-card">
            <div className="constraint-header">
              <label className="constraint-enabled">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={(e) => patchRule(rule.key, { enabled: e.target.checked })}
                />
                <span className="constraint-name">{rule.positionValue || 'New position rule'}</span>
              </label>
            </div>

            <div className="position-rule-fields">
              <label>
                Applies to
                <select
                  value={rule.positionType}
                  onChange={(e) =>
                    patchRule(rule.key, { positionType: e.target.value as 'role' | 'department', positionValue: '' })
                  }
                >
                  <option value="department">Department</option>
                  <option value="role">Specific role</option>
                </select>
              </label>

              {rule.positionType === 'department' ? (
                <label>
                  Department
                  <select
                    value={rule.positionValue}
                    onChange={(e) => patchRule(rule.key, { positionValue: e.target.value })}
                  >
                    <option value="">— select department —</option>
                    {DEPARTMENT_ORDER.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <label>
                  Role
                  <select
                    value={rule.positionValue}
                    onChange={(e) => patchRule(rule.key, { positionValue: e.target.value })}
                  >
                    <option value="">— select role —</option>
                    {roles.map((r) => (
                      <option key={r.role_id} value={r.role_name}>{r.role_name}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>

            <div className="requirement-rows">
              <div className="requirement-row requirement-header">
                <span>Day(s)</span>
                <span>Start</span>
                <span>End</span>
                <span>Minimum needed</span>
                <span />
              </div>
              {rule.requirements.map((req, i) => (
                <div key={i} className="requirement-row">
                  <div className="requirement-days">
                    {DAY_OPTIONS.map((d) => (
                      <label key={d}>
                        <input
                          type="checkbox"
                          checked={req.days.includes(d)}
                          onChange={(e) =>
                            updateRequirement(rule.key, i, {
                              days: e.target.checked
                                ? [...req.days, d]
                                : req.days.filter((day) => day !== d),
                            })
                          }
                        />
                        {d}
                      </label>
                    ))}
                  </div>
                  <input
                    type="time"
                    value={req.start_time}
                    onChange={(e) => updateRequirement(rule.key, i, { start_time: e.target.value })}
                  />
                  <input
                    type="time"
                    value={req.end_time}
                    onChange={(e) => updateRequirement(rule.key, i, { end_time: e.target.value })}
                  />
                  <input
                    type="number"
                    min={0}
                    value={req.min_count ?? ''}
                    onChange={(e) =>
                      updateRequirement(rule.key, i, {
                        min_count: e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                  <button type="button" onClick={() => removeRequirement(rule.key, i)}>Remove</button>
                </div>
              ))}
              <button type="button" onClick={() => addRequirement(rule.key)}>+ Add time slot</button>
            </div>

            <div className="constraint-actions">
              <button onClick={() => handleSave(rule.key)} disabled={rule.saving}>
                {rule.saving ? 'Saving...' : 'Save'}
              </button>
              <button
                type="button"
                className="danger-link"
                onClick={() => handleDelete(rule.key)}
                disabled={rule.deleting}
              >
                {rule.deleting ? 'Removing...' : 'Remove rule'}
              </button>
              {rule.saved && <span className="saved-indicator">Saved</span>}
              {rule.saveError && <span className="error-indicator">{rule.saveError}</span>}
            </div>
          </div>
        ))}
      </div>

      <button type="button" onClick={addRule} className="add-rule-button">+ Add position rule</button>
    </div>
  )
}

export default PositionStaffingManager
