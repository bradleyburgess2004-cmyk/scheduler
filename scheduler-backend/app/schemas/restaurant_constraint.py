from pydantic import BaseModel


class RestaurantConstraintCreate(BaseModel):

    restaurant_id: int
    constraint_id: int
    enabled: bool | None = None
    weight: int | None = None
    parameter_json: dict | None = None


class RestaurantConstraintResponse(RestaurantConstraintCreate):

    config_id: int

    class Config:
        from_attributes = True
