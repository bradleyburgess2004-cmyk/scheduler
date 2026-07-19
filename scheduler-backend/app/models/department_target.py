from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Numeric
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class DepartmentTarget(Base):

    __tablename__ = "department_targets"

    target_id = Column(Integer, primary_key=True, index=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.restaurant_id"))
    department = Column(String(100), nullable=False)
    daily_hours_required = Column(Numeric(8, 2))

    restaurant = relationship("Restaurant", back_populates="department_targets")
