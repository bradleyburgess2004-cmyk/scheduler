from pydantic import BaseModel


class ConstraintCreate(BaseModel):

    name: str | None = None
    description: str | None = None
    class_name: str | None = None


class FieldSpecOut(BaseModel):

    key: str
    label: str
    type: str
    optional: bool = False


class ConstraintResponse(ConstraintCreate):

    constraint_id: int
    parameter_spec: list[FieldSpecOut] | None = None

    class Config:
        from_attributes = True
