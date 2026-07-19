from pydantic import BaseModel


class SkillCreate(BaseModel):

    name: str


class SkillResponse(SkillCreate):

    skill_id: int

    class Config:
        from_attributes = True
