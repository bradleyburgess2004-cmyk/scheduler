from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class GeneratedAssignment(Base):
    """The solver's original baseline pick for a shift, at the moment it
    was generated -- distinct from `assignments`, which is the live,
    editable state a manager can reassign/remove afterward. Diffing
    this table against `assignments` (once a shift's date has passed
    and nothing should be touching it anymore) is how training data for
    a future "predict the manager's actual choice" model gets derived,
    with no separate scheduled job needed -- see
    app/routes/training_data.py.

    Overwritten per-shift, not per-week: solve_schedule() only
    (re)solves shifts whose date hasn't passed yet
    (materialize_shifts_for_week), so a regeneration naturally replaces
    the baseline only for shifts still eligible to be resolved, and
    never touches -- let alone overwrites -- the baseline for a shift
    whose day has already occurred.
    """

    __tablename__ = "generated_assignments"

    id = Column(Integer, primary_key=True, index=True)

    shift_id = Column(Integer, ForeignKey("shifts.shift_id"))
    employee_id = Column(Integer, ForeignKey("employees.employee_id"))

    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    shift = relationship("Shift")
    employee = relationship("Employee")
