from pydantic import BaseModel


class AvailabilityUploadResponse(BaseModel):

    rows_read: int
    employees_updated: int
    windows_applied: int
    orphaned_employee_ids: list[str]
    unmatched_names: list[str]
    created_employees: list[str] = []
