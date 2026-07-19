from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class EmployeeRole(Base):

    __tablename__ = "employee_roles"

    employee_id = Column(Integer, ForeignKey("employees.employee_id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.role_id"), primary_key=True)

    employee = relationship("Employee", back_populates="roles")
    role = relationship("Role", back_populates="employee_roles")
