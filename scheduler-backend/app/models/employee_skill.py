from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class EmployeeSkill(Base):

    __tablename__ = "employee_skills"

    employee_id = Column(Integer, ForeignKey("employees.employee_id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.skill_id"), primary_key=True)

    employee = relationship("Employee", back_populates="skills")
    skill = relationship("Skill", back_populates="employees")
