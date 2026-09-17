from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Restaurant(Base):

    __tablename__ = "restaurants"

    restaurant_id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)
    location = Column(String(200))
    timezone = Column(String(50))

    created_at = Column(DateTime, server_default=func.current_timestamp())

    roles = relationship("Role", back_populates="restaurant")
    employees = relationship("Employee", back_populates="restaurant")
    shift_templates = relationship("ShiftTemplate", back_populates="restaurant")
    shifts = relationship("Shift", back_populates="restaurant")
    restaurant_constraints = relationship("RestaurantConstraint", back_populates="restaurant")
    department_targets = relationship("DepartmentTarget", back_populates="restaurant")
    schedule_templates = relationship("ScheduleTemplate", back_populates="restaurant")
