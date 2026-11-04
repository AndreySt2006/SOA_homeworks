from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BookingCreate(BaseModel):
    user_id: str
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_count: int

class BookingResponse(BaseModel):
    id: str
    user_id: str
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
