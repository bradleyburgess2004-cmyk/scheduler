from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship

from app.database import Base


class Constraint(Base):

    __tablename__ = "constraints"

    constraint_id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100))
    description = Column(Text)
    class_name = Column(String(100))

    restaurant_constraints = relationship("RestaurantConstraint", back_populates="constraint")
