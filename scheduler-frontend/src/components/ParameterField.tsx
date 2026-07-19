import type { Employee, Role } from '../api'
import type { FieldSpec } from '../constraintFormSpecs'
import { DAY_OPTIONS } from '../constraintFormSpecs'

type PairValue = (number | null)[][]

interface Props {
  spec: FieldSpec
  value: unknown
  onChange: (value: unknown) => void
  roles: Role[]
  employees: Employee[]
}

function employeeLabel(e: Employee) {
  return `${e.first_name} ${e.last_name}`
}

function EmployeeSelect({
  value,
  onChange,
  employees,
}: {
  value: number | null
  onChange: (value: number | null) => void
  employees: Employee[]
}) {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
    >
      <option value="">— select employee —</option>
      {employees.map((e) => (
        <option key={e.employee_id} value={e.employee_id}>
          {employeeLabel(e)}
        </option>
      ))}
    </select>
  )
}

function EmployeePairsField({
  value,
  onChange,
  employees,
}: {
  value: PairValue
  onChange: (value: PairValue) => void
  employees: Employee[]
}) {
  function updatePair(index: number, position: 0 | 1, employeeId: number | null) {
    const next = value.map((pair) => [...pair])
    if (!next[index]) next[index] = [null, null]
    next[index][position] = employeeId
    onChange(next)
  }

  function addPair() {
    onChange([...value, [null, null]])
  }

  function removePair(index: number) {
    onChange(value.filter((_, i) => i !== index))
  }

  return (
    <div className="employee-pairs">
      {value.map((pair, i) => (
        <div key={i} className="employee-pair-row">
          <EmployeeSelect value={pair[0] ?? null} onChange={(v) => updatePair(i, 0, v)} employees={employees} />
          <span>&amp;</span>
          <EmployeeSelect value={pair[1] ?? null} onChange={(v) => updatePair(i, 1, v)} employees={employees} />
          <button type="button" onClick={() => removePair(i)}>Remove</button>
        </div>
      ))}
      <button type="button" onClick={addPair}>+ Add pair</button>
    </div>
  )
}

function DayMultiSelect({
  value,
  onChange,
}: {
  value: string[]
  onChange: (value: string[]) => void
}) {
  function toggle(day: string) {
    onChange(value.includes(day) ? value.filter((d) => d !== day) : [...value, day])
  }

  return (
    <div className="day-multi">
      {DAY_OPTIONS.map((d) => (
        <label key={d} className="day-multi-option">
          <input type="checkbox" checked={value.includes(d)} onChange={() => toggle(d)} />
          {d}
        </label>
      ))}
    </div>
  )
}

function ParameterField({ spec, value, onChange, roles, employees }: Props) {
  const label = spec.optional ? `${spec.label} (optional)` : spec.label

  switch (spec.type) {
    case 'number':
      return (
        <label>
          {label}
          <input
            type="number"
            value={value == null ? '' : String(value)}
            onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
          />
        </label>
      )

    case 'time':
      return (
        <label>
          {label}
          <input
            type="time"
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onChange(e.target.value || null)}
          />
        </label>
      )

    case 'text':
      return (
        <label>
          {label}
          <input
            type="text"
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onChange(e.target.value)}
          />
        </label>
      )

    case 'day':
      return (
        <label>
          {label}
          <select value={typeof value === 'string' ? value : ''} onChange={(e) => onChange(e.target.value || null)}>
            <option value="">— select day —</option>
            {DAY_OPTIONS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
      )

    case 'role':
      return (
        <label>
          {label}
          <select value={typeof value === 'string' ? value : ''} onChange={(e) => onChange(e.target.value || null)}>
            <option value="">— select role —</option>
            {roles.map((r) => (
              <option key={r.role_id} value={r.role_name}>{r.role_name}</option>
            ))}
          </select>
        </label>
      )

    case 'employee':
      return (
        <label>
          {label}
          <EmployeeSelect
            value={typeof value === 'number' ? value : null}
            onChange={onChange}
            employees={employees}
          />
        </label>
      )

    case 'employee_pairs':
      return (
        <div className="field-block">
          <span className="field-label">{label}</span>
          <EmployeePairsField
            value={Array.isArray(value) ? (value as PairValue) : []}
            onChange={onChange}
            employees={employees}
          />
        </div>
      )

    case 'day_multi':
      return (
        <div className="field-block">
          <span className="field-label">{label}</span>
          <DayMultiSelect
            value={Array.isArray(value) ? (value as string[]) : []}
            onChange={onChange}
          />
        </div>
      )

    case 'date':
      return (
        <label>
          {label}
          <input
            type="date"
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onChange(e.target.value || null)}
          />
        </label>
      )

    case 'boolean':
      return (
        <label className="constraint-enabled">
          <input
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
          />
          {label}
        </label>
      )

    default:
      return null
  }
}

export default ParameterField
