from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.skill import Skill

from app.schemas.skill import SkillCreate
from app.schemas.skill import SkillResponse

router = APIRouter(
    prefix="/skills",
    tags=["Skills"]
)


@router.get("/", response_model=list[SkillResponse])
def get_skills(db: Session = Depends(get_db)):

    return db.query(Skill).all()


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(skill_id: int, db: Session = Depends(get_db)):

    skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return skill


@router.post("/", response_model=SkillResponse)
def create_skill(skill: SkillCreate, db: Session = Depends(get_db)):

    db_skill = Skill(**skill.model_dump())

    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)

    return db_skill


@router.put("/{skill_id}", response_model=SkillResponse)
def update_skill(skill_id: int, skill: SkillCreate, db: Session = Depends(get_db)):

    db_skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()

    if not db_skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    for field, value in skill.model_dump().items():
        setattr(db_skill, field, value)

    db.commit()
    db.refresh(db_skill)

    return db_skill


@router.delete("/{skill_id}", status_code=204)
def delete_skill(skill_id: int, db: Session = Depends(get_db)):

    db_skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()

    if not db_skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    db.delete(db_skill)
    db.commit()
