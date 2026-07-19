from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Date
from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class TimeOffRequest(Base):

    __tablename__ = "time_off_requests"

    request_id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(Integer, ForeignKey("employees.employee_id"))

    start_date = Column(Date)
    end_date = Column(Date)
    approved = Column(Boolean)

    employee = relationship("Employee", back_populates="time_off_requests")
