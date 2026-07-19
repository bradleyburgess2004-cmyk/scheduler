from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class RestaurantConstraint(Base):

    __tablename__ = "restaurant_constraints"

    config_id = Column(Integer, primary_key=True, index=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.restaurant_id"))
    constraint_id = Column(Integer, ForeignKey("constraints.constraint_id"))

    enabled = Column(Boolean)
    weight = Column(Integer)
    parameter_json = Column(JSONB)

    restaurant = relationship("Restaurant", back_populates="restaurant_constraints")
    constraint = relationship("Constraint", back_populates="restaurant_constraints")
