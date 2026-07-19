from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Date,
    Boolean,
    ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    restaurant_id = Column(
        Integer,
        ForeignKey("restaurants.restaurant_id"),
        nullable=True
    )

    first_name = Column(
        String(50),
        nullable=True
    )

    last_name = Column(
        String(50),
        nullable=True
    )

    role_id = Column(
        Integer,
        ForeignKey("roles.role_id"),
        nullable=True
    )

    hourly_rate = Column(
        Numeric(8, 2),
        nullable=True
    )

    hire_date = Column(
        Date,
        nullable=True
    )

    active = Column(
        Boolean,
        default=True
    )

    max_weekly_hours = Column(
        Integer,
        nullable=True
    )

    overtime_limit = Column(
        Integer,
        nullable=True
    )

    external_employee_id = Column(
        String(50),
        unique=True,
        nullable=True
    )

    min_weekly_hours = Column(
        Integer,
        nullable=True
    )


    # Relationships
    restaurant = relationship(
        "Restaurant",
        back_populates="employees"
    )

    role = relationship(
        "Role",
        back_populates="employees"
    )

    skills = relationship(
        "EmployeeSkill",
        back_populates="employee"
    )

    availability = relationship(
        "Availability",
        back_populates="employee"
    )

    time_off_requests = relationship(
        "TimeOffRequest",
        back_populates="employee"
    )

    assignments = relationship(
        "Assignment",
        back_populates="employee"
    )

    roles = relationship(
        "EmployeeRole",
        back_populates="employee"
    )

