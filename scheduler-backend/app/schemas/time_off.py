from datetime import date

from pydantic import BaseModel


class TimeOffRecord(BaseModel):

    employee_name: str
    employee_id: int | None
    start_date: date
    end_date: date
    status: str


class TimeOffParseResponse(BaseModel):

    records: list[TimeOffRecord]


class TimeOffApplyRequest(BaseModel):

    records: list[TimeOffRecord]


class TimeOffApplyResponse(BaseModel):

    days_blocked: int
    requests_applied: int
    requests_skipped_not_approved: int
    requests_skipped_unmatched: int
