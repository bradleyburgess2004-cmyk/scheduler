from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant_constraint import RestaurantConstraint

from app.schemas.restaurant_constraint import RestaurantConstraintCreate
from app.schemas.restaurant_constraint import RestaurantConstraintResponse

router = APIRouter(
    prefix="/restaurant-constraints",
    tags=["Restaurant Constraints"]
)


@router.get("/", response_model=list[RestaurantConstraintResponse])
def get_restaurant_constraints(db: Session = Depends(get_db)):

    return db.query(RestaurantConstraint).all()


@router.get("/{config_id}", response_model=RestaurantConstraintResponse)
def get_restaurant_constraint(config_id: int, db: Session = Depends(get_db)):

    config = db.query(RestaurantConstraint).filter(RestaurantConstraint.config_id == config_id).first()

    if not config:
        raise HTTPException(status_code=404, detail="Restaurant constraint not found")

    return config


@router.post("/", response_model=RestaurantConstraintResponse)
def create_restaurant_constraint(restaurant_constraint: RestaurantConstraintCreate,
                                  db: Session = Depends(get_db)):

    db_config = RestaurantConstraint(**restaurant_constraint.model_dump())

    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    return db_config


@router.put("/{config_id}", response_model=RestaurantConstraintResponse)
def update_restaurant_constraint(config_id: int,
                                  restaurant_constraint: RestaurantConstraintCreate,
                                  db: Session = Depends(get_db)):

    db_config = db.query(RestaurantConstraint).filter(RestaurantConstraint.config_id == config_id).first()

    if not db_config:
        raise HTTPException(status_code=404, detail="Restaurant constraint not found")

    for field, value in restaurant_constraint.model_dump().items():
        setattr(db_config, field, value)

    db.commit()
    db.refresh(db_config)

    return db_config


@router.delete("/{config_id}", status_code=204)
def delete_restaurant_constraint(config_id: int, db: Session = Depends(get_db)):

    db_config = db.query(RestaurantConstraint).filter(RestaurantConstraint.config_id == config_id).first()

    if not db_config:
        raise HTTPException(status_code=404, detail="Restaurant constraint not found")

    db.delete(db_config)
    db.commit()
