import { useState } from 'react'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import type { Role, ScheduledShift } from '../api'

export function shiftChipId(employeeId: number, date: string, shiftId: number): string {
  return `chip:${employeeId}:${date}:${shiftId}`
}

export function cellDropId(employeeId: number, date: string): string {
  return `cell:${employeeId}:${date}`
}

export interface ShiftEdit {
  start_time: string
  end_time: string
  role_id: number
  role_name: string
}

interface ChipProps {
  employeeId: number
  date: string
  shift: ScheduledShift
  roles: Role[]
  onRemove: () => void
  onEdit: (edit: ShiftEdit) => void
}

export function DraggableShiftChip({ employeeId, date, shift, roles, onRemove, onEdit }: ChipProps) {
  const [editing, setEditing] = useState(false)
  const [startTime, setStartTime] = useState(shift.start_time.slice(0, 5))
  const [endTime, setEndTime] = useState(shift.end_time.slice(0, 5))
  const [roleId, setRoleId] = useState(shift.role_id)

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: shiftChipId(employeeId, date, shift.shift_id),
    data: { shift },
    disabled: editing,
  })

  function beginEdit() {
    setStartTime(shift.start_time.slice(0, 5))
    setEndTime(shift.end_time.slice(0, 5))
    setRoleId(shift.role_id)
    setEditing(true)
  }

  function saveEdit() {
    const role = roles.find((r) => r.role_id === roleId)
    onEdit({
      start_time: `${startTime}:00`,
      end_time: `${endTime}:00`,
      role_id: roleId,
      role_name: role?.role_name ?? shift.role_name,
    })
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="shift-chip shift-chip-editing">
        <select value={roleId} onChange={(e) => setRoleId(Number(e.target.value))}>
          {roles.map((r) => (
            <option key={r.role_id} value={r.role_id}>{r.role_name}</option>
          ))}
        </select>
        <div className="shift-edit-times">
          <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </div>
        <div className="shift-edit-actions">
          <button type="button" onClick={saveEdit}>Save</button>
          <button type="button" onClick={() => setEditing(false)}>Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={setNodeRef}
      className={`shift-chip ${shift.understaffed ? 'understaffed' : ''} ${isDragging ? 'dragging' : ''}`}
      {...listeners}
      {...attributes}
    >
      <div className="shift-chip-header">
        <span className="shift-role">{shift.role_name}</span>
        <span className="shift-chip-buttons">
          <button
            type="button"
            className="shift-edit"
            title="Edit time / position"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={beginEdit}
          >
            ✎
          </button>
          <button
            type="button"
            className="shift-remove"
            title="Remove this assignment"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={onRemove}
          >
            ×
          </button>
        </span>
      </div>
      <div className="shift-time">
        {shift.start_time.slice(0, 5)}–{shift.end_time.slice(0, 5)}
      </div>
    </div>
  )
}

export type AvailabilityStatus = 'available' | 'unavailable' | 'unknown'

interface CellProps {
  employeeId: number
  date: string
  children: React.ReactNode
  availabilityStatus?: AvailabilityStatus
  availabilityTitle?: string
}

export function DroppableCell({ employeeId, date, children, availabilityStatus, availabilityTitle }: CellProps) {
  const { setNodeRef, isOver } = useDroppable({ id: cellDropId(employeeId, date) })
  const statusClass = availabilityStatus ? `availability-${availabilityStatus}` : ''
  return (
    <td
      ref={setNodeRef}
      className={`${isOver ? 'drop-hover' : ''} ${statusClass}`.trim()}
      title={availabilityTitle}
    >
      {children}
    </td>
  )
}

export function ShiftChipPreview({ shift }: { shift: ScheduledShift }) {
  return (
    <div className={`shift-chip dragging-overlay ${shift.understaffed ? 'understaffed' : ''}`}>
      <div className="shift-chip-header">
        <span className="shift-role">{shift.role_name}</span>
      </div>
      <div className="shift-time">
        {shift.start_time.slice(0, 5)}–{shift.end_time.slice(0, 5)}
      </div>
    </div>
  )
}
