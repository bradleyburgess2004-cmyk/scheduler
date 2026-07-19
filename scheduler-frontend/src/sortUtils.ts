export type SortKey = 'name' | 'role' | 'wage'

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'role', label: 'Role' },
  { value: 'wage', label: 'Wage' },
]
