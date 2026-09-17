from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Time
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ScheduleTemplateEntry(Base):
    """One (employee, day-of-week, start_time, end_time) cell from a
    parsed ScheduleTemplate CSV. Role is intentionally not stored here --
    matching against a target week's shifts uses the employee's current
    `Employee.role_id` instead, see
    app/optimizer/constraints/template_adherence.py.
    """

    __tablename__ = "schedule_template_entries"

    entry_id = Column(Integer, primary_key=True, index=True)

    template_id = Column(Integer, ForeignKey("schedule_templates.template_id"))
    employee_id = Column(Integer, ForeignKey("employees.employee_id"))

    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    template = relationship("ScheduleTemplate", back_populates="entries")
    employee = relationship("Employee")
