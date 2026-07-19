from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Date
from sqlalchemy import Time
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Shift(Base):

    __tablename__ = "shifts"

    shift_id = Column(Integer, primary_key=True, index=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.restaurant_id"))
    role_id = Column(Integer, ForeignKey("roles.role_id"))

    shift_date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)

    required_employees = Column(Integer)

    restaurant = relationship("Restaurant", back_populates="shifts")
    role = relationship("Role", back_populates="shifts")
    assignments = relationship("Assignment", back_populates="shift")
