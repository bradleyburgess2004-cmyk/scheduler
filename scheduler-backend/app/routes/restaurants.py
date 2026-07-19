from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant

from app.schemas.restaurant import RestaurantCreate
from app.schemas.restaurant import RestaurantResponse

router = APIRouter(
    prefix="/restaurants",
    tags=["Restaurants"]
)


@router.get("/", response_model=list[RestaurantResponse])
def get_restaurants(db: Session = Depends(get_db)):

    return db.query(Restaurant).all()


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)):

    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()

    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    return restaurant


@router.post("/", response_model=RestaurantResponse)
def create_restaurant(restaurant: RestaurantCreate,
                       db: Session = Depends(get_db)):

    db_restaurant = Restaurant(**restaurant.model_dump())

    db.add(db_restaurant)
    db.commit()
    db.refresh(db_restaurant)

    return db_restaurant


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
def update_restaurant(restaurant_id: int,
                       restaurant: RestaurantCreate,
                       db: Session = Depends(get_db)):

    db_restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()

    if not db_restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    for field, value in restaurant.model_dump().items():
        setattr(db_restaurant, field, value)

    db.commit()
    db.refresh(db_restaurant)

    return db_restaurant


@router.delete("/{restaurant_id}", status_code=204)
def delete_restaurant(restaurant_id: int, db: Session = Depends(get_db)):

    db_restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()

    if not db_restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    db.delete(db_restaurant)
    db.commit()
