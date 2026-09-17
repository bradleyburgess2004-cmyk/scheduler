from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class ScheduleTemplate(Base):
    """A saved, reviewed CSV upload of a past/desired weekly shift
    pattern (one row per employee, one column per day of week). Used to
    softly bias `solve_schedule()` toward reproducing this pattern when
    generating a new week's schedule -- see
    app/optimizer/constraints/template_adherence.py.
    """

    __tablename__ = "schedule_templates"

    template_id = Column(Integer, primary_key=True, index=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.restaurant_id"))
    name = Column(String(100), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="schedule_templates")
    entries = relationship(
        "ScheduleTemplateEntry",
        back_populates="template",
        cascade="all, delete-orphan",
    )
