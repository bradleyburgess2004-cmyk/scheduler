from datetime import datetime
from pydantic import BaseModel


class RestaurantCreate(BaseModel):

    name: str
    location: str | None = None
    timezone: str | None = None


class RestaurantResponse(RestaurantCreate):

    restaurant_id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True
