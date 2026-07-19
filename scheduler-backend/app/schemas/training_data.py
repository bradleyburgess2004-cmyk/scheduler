from datetime import date, time

from pydantic import BaseModel


class TrainingDataRow(BaseModel):
    """One past shift, diffed: what the solver originally picked
    (baseline, from generated_assignments) vs what the live
    `assignments` table says now. Only ever computed for shifts whose
    date has already passed -- see app/routes/training_data.py."""

    shift_id: int
    shift_date: date
    role_id: int
    role_name: str
    start_time: time
    end_time: time
    required_employees: int
    baseline_employee_ids: list[int]
    final_employee_ids: list[int]
    changed: bool
