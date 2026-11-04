from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class FlightStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class ReservationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"

class Flight(Base):
    __tablename__ = "flights"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_number = Column(String, nullable=False)
    airline = Column(String, nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(Enum(FlightStatus), default=FlightStatus.SCHEDULED)

    __table_args__ = (
        CheckConstraint("total_seats > 0"),
        CheckConstraint("available_seats >= 0"),
        CheckConstraint("price > 0"),
        UniqueConstraint("flight_number", "departure_time", name="uq_flight_date"),
    )

class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_id = Column(String, nullable=False)
    booking_id = Column(String, nullable=False, unique=True)
    seat_count = Column(Integer, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        CheckConstraint("seat_count > 0"),
    )
