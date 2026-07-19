from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Time
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ShiftTemplate(Base):

    __tablename__ = "shift_templates"

    template_id = Column(Integer, primary_key=True, index=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.restaurant_id"))
    role_id = Column(Integer, ForeignKey("roles.role_id"))

    start_time = Column(Time)
    end_time = Column(Time)

    day_of_week = Column(Integer)
    required_count = Column(Integer)

    restaurant = relationship("Restaurant", back_populates="shift_templates")
    role = relationship("Role", back_populates="shift_templates")
