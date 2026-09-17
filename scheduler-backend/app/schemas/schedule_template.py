from datetime import datetime
from datetime import time

from pydantic import BaseModel

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


class ScheduleTemplateEntryOut(BaseModel):

    entry_id: int | None = None
    raw_employee_label: str
    employee_id: int | None
    employee_name: str | None
    day_of_week: int
    day_name: str
    start_time: time
    end_time: time


class ScheduleTemplateParseResponse(BaseModel):

    rows_read: int
    entries: list[ScheduleTemplateEntryOut]
    unmatched_labels: list[str]
    unparsed_cells: list[str]


class ScheduleTemplateSaveRequest(BaseModel):

    name: str
    entries: list[ScheduleTemplateEntryOut]


class ScheduleTemplateSaveResponse(BaseModel):

    template_id: int
    name: str
    entries_saved: int
    entries_skipped_unmatched: int


class ScheduleTemplateSummary(BaseModel):

    template_id: int
    name: str
    created_at: datetime
    entry_count: int

    class Config:
        from_attributes = True
