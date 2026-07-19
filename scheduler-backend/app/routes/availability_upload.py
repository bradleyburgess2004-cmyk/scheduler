import csv
import io

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant
from app.models.employee import Employee

from app.scripts.import_weekly_workflow import (
    import_availability,
    import_availability_wide,
    is_wide_availability_format,
)

from app.schemas.availability_upload import AvailabilityUploadResponse

router = APIRouter(
    prefix="/restaurants",
    tags=["Availability Upload"]
)


@router.post("/{restaurant_id}/availability/upload", response_model=AvailabilityUploadResponse)
async def upload_availability(
    restaurant_id: int,
    file: UploadFile = File(...),
    auto_create_employees: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Uploads this week's availability for a restaurant. Accepts either
    format, no pre-formatting needed:

    - the raw HotSchedules export (first column is the employee's full
      name, remaining columns are one per day -- 'Available All Day',
      'Unavailable All Day', 'Partially Available H:MM AM/PM - H:MM
      AM/PM'), matched to employees by name; or
    - our own long format (employee_id, day, start_time, end_time),
      matched by external_employee_id.

    Either way, for every employee found in the file their existing
    availability is fully replaced -- this is what makes a re-upload
    override the previous week's availability rather than append to
    it. Anyone in the file who doesn't match an existing employee is
    reported back, not silently dropped -- unless auto_create_employees
    is set, in which case an unmatched name in the (wide-format only --
    the long format has no name to create a record from, just an
    external_employee_id) file gets a new Employee row created and
    their availability from this file applied immediately."""

    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV")

    try:
        header = next(csv.reader(io.StringIO(text)))
    except StopIteration:
        raise HTTPException(status_code=400, detail="File is empty")

    employees = db.query(Employee).filter(Employee.restaurant_id == restaurant_id).all()

    try:
        if is_wide_availability_format(header):
            employees_by_name = {
                f"{e.first_name} {e.last_name}".lower(): e for e in employees
            }
            stats = import_availability_wide(
                db, employees_by_name, text, restaurant_id, auto_create_employees
            )
        else:
            employees_by_ext_id = {
                e.external_employee_id: e for e in employees if e.external_employee_id
            }
            rows = list(csv.DictReader(io.StringIO(text)))
            stats = import_availability(db, employees_by_ext_id, rows)
        db.commit()
    except (ValueError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not parse availability file: {e}")

    return AvailabilityUploadResponse(**stats)
