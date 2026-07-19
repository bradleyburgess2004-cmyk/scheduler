from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import Integer
from sqlalchemy import Time
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Availability(Base):

    __tablename__ = "availability"

    availability_id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(Integer, ForeignKey("employees.employee_id"))

    day_of_week = Column(Integer)
    start_time = Column(Time)
    end_time = Column(Time)

    # The specific calendar date this window applies to, when known (set
    # by the wide-format/HotSchedules CSV upload, which has real dates in
    # its header). NULL means a legacy/undated recurring day-of-week
    # pattern -- see load_availability() in app/optimizer/scheduler.py for
    # how dated rows take priority over these per employee, per week.
    availability_date = Column(Date, nullable=True)

    employee = relationship("Employee", back_populates="availability")
