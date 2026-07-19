import { useEffect, useMemo, useRef, useState } from 'react'
import {
  getEmployees,
  getRoles,
  getEmployeeRoles,
  createEmployee,
  updateEmployee,
  deleteEmployee,
  createEmployeeRole,
  deleteEmployeeRole,
  type Employee,
  type Role,
  type EmployeeRole,
  type EmployeeInput,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { SORT_OPTIONS, type SortKey } from '../sortUtils'
import './Employees.css'

const EMPTY_FORM: EmployeeInput = {
  restaurant_id: 0,
  first_name: '',
  last_name: '',
  role_id: null,
  active: true,
  hourly_rate: null,
  max_weekly_hours: null,
  min_weekly_hours: null,
}

function RoleMultiSelectDropdown({
  roles,
  selectedRoleIds,
  onToggle,
}: {
  roles: Role[]
  selectedRoleIds: number[]
  onToggle: (roleId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectedNames = roles
    .filter((r) => selectedRoleIds.includes(r.role_id))
    .map((r) => r.role_name)

  const summary = selectedNames.length > 0 ? selectedNames.join(', ') : '— select roles —'

  return (
    <div className="role-multi-dropdown" ref={containerRef}>
      <button
        type="button"
        className="role-multi-dropdown-toggle"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="role-multi-dropdown-summary">{summary}</span>
        <span className="role-multi-dropdown-arrow">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="role-multi-dropdown-panel">
          {roles.map((r) => (
            <label key={r.role_id} className="role-multi-option">
              <input
                type="checkbox"
                checked={selectedRoleIds.includes(r.role_id)}
                onChange={() => onToggle(r.role_id)}
              />
              {r.role_name}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

function Employees() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()

  const [employees, setEmployees] = useState<Employee[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [employeeRoles, setEmployeeRoles] = useState<EmployeeRole[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<EmployeeInput>(EMPTY_FORM)
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  function loadAll() {
    setLoading(true)
    setError(null)
    Promise.all([getEmployees(), getRoles(), getEmployeeRoles()])
      .then(([e, r, er]) => {
        setEmployees(e)
        setRoles(r)
        setEmployeeRoles(er)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadAll, [])

  const roleNameById = useMemo(() => {
    const map = new Map<number, string>()
    roles.forEach((r) => map.set(r.role_id, r.role_name))
    return map
  }, [roles])

  const roleNamesByEmployeeId = useMemo(() => {
    const map = new Map<number, string[]>()
    employeeRoles.forEach((er) => {
      const name = roleNameById.get(er.role_id)
      if (!name) return
      const list = map.get(er.employee_id) ?? []
      list.push(name)
      map.set(er.employee_id, list)
    })
    return map
  }, [employeeRoles, roleNameById])

  const visibleEmployees = useMemo(() => {
    const term = search.trim().toLowerCase()
    const filtered = term
      ? employees.filter((e) => `${e.first_name} ${e.last_name}`.toLowerCase().includes(term))
      : [...employees]

    filtered.sort((a, b) => {
      const nameA = `${a.last_name} ${a.first_name}`
      const nameB = `${b.last_name} ${b.first_name}`
      if (sortKey === 'role') {
        const roleA = (a.role_id != null ? roleNameById.get(a.role_id) : undefined) ?? ''
        const roleB = (b.role_id != null ? roleNameById.get(b.role_id) : undefined) ?? ''
        return roleA.localeCompare(roleB) || nameA.localeCompare(nameB)
      }
      if (sortKey === 'wage') {
        const wageA = a.hourly_rate ? Number(a.hourly_rate) : 0
        const wageB = b.hourly_rate ? Number(b.hourly_rate) : 0
        return wageB - wageA || nameA.localeCompare(nameB)
      }
      return nameA.localeCompare(nameB)
    })

    return filtered
  }, [employees, search, sortKey, roleNameById])

  function openCreateForm() {
    setEditingId(null)
    setForm({ ...EMPTY_FORM, restaurant_id: restaurant?.restaurant_id ?? 0 })
    setSelectedRoleIds([])
    setSaveError(null)
    setShowForm(true)
  }

  function openEditForm(emp: Employee) {
    setEditingId(emp.employee_id)
    setForm({
      restaurant_id: emp.restaurant_id,
      first_name: emp.first_name,
      last_name: emp.last_name,
      role_id: emp.role_id,
      active: emp.active,
      hourly_rate: emp.hourly_rate ? Number(emp.hourly_rate) : null,
      max_weekly_hours: emp.max_weekly_hours,
      min_weekly_hours: emp.min_weekly_hours,
    })
    // Union of this employee's employee_roles rows (what the solver actually
    // uses for eligibility) with their legacy single role_id, in case that
    // was set before this checkbox selector existed and has no matching row.
    const existingRoleIds = employeeRoles
      .filter((er) => er.employee_id === emp.employee_id)
      .map((er) => er.role_id)
    const initialSelection = new Set(existingRoleIds)
    if (emp.role_id != null) initialSelection.add(emp.role_id)
    setSelectedRoleIds([...initialSelection])
    setSaveError(null)
    setShowForm(true)
  }

  function toggleRole(roleId: number) {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId) ? prev.filter((id) => id !== roleId) : [...prev, roleId]
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      // Primary role_id is now just a display/sort convenience derived from
      // the checked set (first in the restaurant's role order) -- the
      // solver only reads the employee_roles rows synced below.
      const primaryRoleId = roles.find((r) => selectedRoleIds.includes(r.role_id))?.role_id ?? null
      const submittedForm = { ...form, role_id: primaryRoleId }

      const employeeId = editingId !== null
        ? (await updateEmployee(editingId, submittedForm)).employee_id
        : (await createEmployee(submittedForm)).employee_id

      const existingRoleIds = new Set(
        employeeRoles.filter((er) => er.employee_id === employeeId).map((er) => er.role_id)
      )
      const selected = new Set(selectedRoleIds)
      const toAdd = [...selected].filter((id) => !existingRoleIds.has(id))
      const toRemove = [...existingRoleIds].filter((id) => !selected.has(id))

      await Promise.all([
        ...toAdd.map((roleId) => createEmployeeRole({ employee_id: employeeId, role_id: roleId })),
        ...toRemove.map((roleId) => deleteEmployeeRole(employeeId, roleId)),
      ])

      setShowForm(false)
      loadAll()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(emp: Employee) {
    const confirmed = window.confirm(
      `Permanently delete ${emp.first_name} ${emp.last_name}? This also removes their ` +
        `assignments, availability, roles, and time-off requests. This cannot be undone.`
    )
    if (!confirmed) return

    setDeletingId(emp.employee_id)
    setDeleteError(null)
    try {
      await deleteEmployee(emp.employee_id)
      loadAll()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err))
    } finally {
      setDeletingId(null)
    }
  }

  if (restaurantLoading) return <p>Loading...</p>
  if (restaurantError) return <p className="form-error">{restaurantError}</p>

  return (
    <div>
      <h1>Employees</h1>

      <div className="employees-controls">
        <input
          type="text"
          placeholder="Search employee..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="sort-control">
          Sort by
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <button className="primary" onClick={openCreateForm}>+ Add employee</button>
      </div>

      {loading && <p>Loading employees...</p>}
      {error && <p className="form-error">Failed to load employees: {error}</p>}

      {!loading && !error && (
        <>
          <p className="employees-count">{visibleEmployees.length} of {employees.length} employees</p>
          {deleteError && <p className="form-error">Failed to delete employee: {deleteError}</p>}
          <table className="employees-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Roles</th>
                <th>Hourly Rate</th>
                <th>Min / Max Hrs</th>
                <th>Active</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visibleEmployees.map((emp) => (
                <tr key={emp.employee_id} className={emp.active ? '' : 'inactive'}>
                  <td>{emp.first_name} {emp.last_name}</td>
                  <td>{(roleNamesByEmployeeId.get(emp.employee_id) ?? []).join(', ')}</td>
                  <td>{emp.hourly_rate ? `$${emp.hourly_rate}/hr` : '—'}</td>
                  <td>{emp.min_weekly_hours ?? '—'} / {emp.max_weekly_hours ?? '—'}</td>
                  <td>{emp.active ? 'Active' : 'Inactive'}</td>
                  <td className="employee-row-actions">
                    <button onClick={() => openEditForm(emp)}>Edit</button>
                    <button
                      className="danger-link"
                      onClick={() => handleDelete(emp)}
                      disabled={deletingId === emp.employee_id}
                    >
                      {deletingId === emp.employee_id ? 'Deleting...' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {showForm && (
        <div className="employee-form-overlay" onClick={() => setShowForm(false)}>
          <form
            className="employee-form"
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSubmit}
          >
            <h2>{editingId !== null ? 'Edit employee' : 'Add employee'}</h2>

            <label>
              First name
              <input
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
            </label>

            <label>
              Last name
              <input
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </label>

            <div className="field-block">
              <span className="field-label">Primary role(s)</span>
              <RoleMultiSelectDropdown roles={roles} selectedRoleIds={selectedRoleIds} onToggle={toggleRole} />
            </div>

            <label>
              Status
              <select
                value={form.active === false ? 'inactive' : 'active'}
                onChange={(e) => setForm({ ...form, active: e.target.value !== 'inactive' })}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>

            <label>
              Hourly rate
              <input
                type="number"
                step="0.01"
                value={form.hourly_rate ?? ''}
                onChange={(e) =>
                  setForm({ ...form, hourly_rate: e.target.value ? Number(e.target.value) : null })
                }
              />
            </label>

            <label>
              Min weekly hours
              <input
                type="number"
                value={form.min_weekly_hours ?? ''}
                onChange={(e) =>
                  setForm({ ...form, min_weekly_hours: e.target.value ? Number(e.target.value) : null })
                }
              />
            </label>

            <label>
              Max weekly hours
              <input
                type="number"
                value={form.max_weekly_hours ?? ''}
                onChange={(e) =>
                  setForm({ ...form, max_weekly_hours: e.target.value ? Number(e.target.value) : null })
                }
              />
            </label>

            {saveError && <p className="form-error">{saveError}</p>}

            <div className="employee-form-actions">
              <button type="button" onClick={() => setShowForm(false)}>Cancel</button>
              <button type="submit" className="primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

export default Employees
