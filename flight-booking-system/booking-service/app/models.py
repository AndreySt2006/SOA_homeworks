from sqlalchemy import Column, String, Integer, Float, DateTime, Enum
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class BookingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    flight_id = Column(String, nullable=False)
    passenger_name = Column(String, nullable=False)
    passenger_email = Column(String, nullable=False)
    seat_count = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.CONFIRMED)
    created_at = Column(DateTime, default=datetime.utcnow)
