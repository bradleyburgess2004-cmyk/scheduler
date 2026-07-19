from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Role(Base):

    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, index=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.restaurant_id"))
    role_name = Column(String(50), nullable=False)
    department = Column(String(50))

    restaurant = relationship("Restaurant", back_populates="roles")
    employees = relationship("Employee", back_populates="role")
    shift_templates = relationship("ShiftTemplate", back_populates="role")
    shifts = relationship("Shift", back_populates="role")
    employee_roles = relationship("EmployeeRole", back_populates="role")
