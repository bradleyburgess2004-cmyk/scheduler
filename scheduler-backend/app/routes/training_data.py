from collections import defaultdict
from datetime import date

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant
from app.models.role import Role
from app.models.shift import Shift
from app.models.assignment import Assignment
from app.models.generated_assignment import GeneratedAssignment

from app.schemas.training_data import TrainingDataRow

router = APIRouter(
    prefix="/restaurants",
    tags=["Training Data"],
)


@router.get("/{restaurant_id}/training-data", response_model=list[TrainingDataRow])
def get_training_data(
    restaurant_id: int,
    start_date: date | None = Query(None, description="Only shifts on/after this date"),
    end_date: date | None = Query(None, description="Only shifts on/before this date"),
    db: Session = Depends(get_db),
):
    """Diffs each past shift's solver baseline (generated_assignments)
    against its current live state (assignments) -- the raw material
    for training a "predict the manager's actual choice" model. No
    scheduled job involved: this reads current DB state on demand, so
    it always reflects the latest truth, including any late/retroactive
    correction a manager makes days after a shift occurred.

    Only shifts whose date has already passed are included --
    solve_schedule() never touches those again (materialize_shifts_for_week
    excludes past dates), so their assignments are stable, permanent
    history rather than something still being actively edited."""

    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    query = (
        db.query(Shift, Role.role_name)
        .join(Role, Role.role_id == Shift.role_id)
        .filter(Shift.restaurant_id == restaurant_id, Shift.shift_date < date.today())
    )
    if start_date is not None:
        query = query.filter(Shift.shift_date >= start_date)
    if end_date is not None:
        query = query.filter(Shift.shift_date <= end_date)

    shift_rows = query.all()
    shift_ids = [shift.shift_id for shift, _ in shift_rows]

    baseline_by_shift = defaultdict(list)
    for ga in db.query(GeneratedAssignment).filter(GeneratedAssignment.shift_id.in_(shift_ids)).all():
        baseline_by_shift[ga.shift_id].append(ga.employee_id)

    final_by_shift = defaultdict(list)
    for a in db.query(Assignment).filter(Assignment.shift_id.in_(shift_ids)).all():
        final_by_shift[a.shift_id].append(a.employee_id)

    rows = []
    for shift, role_name in shift_rows:
        baseline = sorted(baseline_by_shift.get(shift.shift_id, []))
        final = sorted(final_by_shift.get(shift.shift_id, []))
        rows.append(TrainingDataRow(
            shift_id=shift.shift_id,
            shift_date=shift.shift_date,
            role_id=shift.role_id,
            role_name=role_name,
            start_time=shift.start_time,
            end_time=shift.end_time,
            required_employees=shift.required_employees or 1,
            baseline_employee_ids=baseline,
            final_employee_ids=final,
            changed=baseline != final,
        ))

    rows.sort(key=lambda r: r.shift_date)
    return rows
