from datetime import date
from typing import Literal, Union

from pydantic import BaseModel


class AiInterpretRequest(BaseModel):

    prompt: str


class ConstraintProposal(BaseModel):

    action: Literal["configure_constraint"] = "configure_constraint"
    constraint_id: int | None
    class_name: str
    constraint_name: str | None
    existing_config_id: int | None
    enabled: bool
    weight: int | None
    parameter_json: dict
    validation_errors: list[str]
    warnings: list[str]

    class Config:
        from_attributes = True


class ScheduleGenerationProposal(BaseModel):

    action: Literal["generate_schedule"] = "generate_schedule"
    week_start: date
    time_limit: int
    validation_errors: list[str]
    warnings: list[str]

    class Config:
        from_attributes = True


class AiInterpretResponse(BaseModel):

    proposal: Union[ConstraintProposal, ScheduleGenerationProposal]


class AiConfirmConstraintRequest(BaseModel):

    action: Literal["configure_constraint"]
    constraint_id: int
    existing_config_id: int | None = None
    enabled: bool
    weight: int | None = None
    parameter_json: dict


class AiConfirmScheduleRequest(BaseModel):

    action: Literal["generate_schedule"]
    week_start: date
    time_limit: int = 120


class ChatTurn(BaseModel):

    role: Literal["user", "assistant"]
    content: str


class AiChatRequest(BaseModel):

    message: str
    history: list[ChatTurn] = []


class PendingSchedule(BaseModel):

    week_start: date
    time_limit: int


class AiChatResponse(BaseModel):

    reply: str
    applied: bool
    pending_schedule: PendingSchedule | None = None
