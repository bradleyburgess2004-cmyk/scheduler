from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Assignment(Base):

    __tablename__ = "assignments"

    assignment_id = Column(Integer, primary_key=True, index=True)

    shift_id = Column(Integer, ForeignKey("shifts.shift_id"))
    employee_id = Column(Integer, ForeignKey("employees.employee_id"))

    shift = relationship("Shift", back_populates="assignments")
    employee = relationship("Employee", back_populates="assignments")
