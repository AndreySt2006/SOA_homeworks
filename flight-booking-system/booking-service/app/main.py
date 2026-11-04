from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging
import grpc
import uuid
from .database import get_db, init_db
from .models import Booking, BookingStatus
from .schemas import BookingCreate, BookingResponse
from .grpc_client import flight_client
from .circuit_breaker import CircuitBreaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Booking Service")

@app.on_event("startup")
def startup():
    init_db()
    logger.info("Booking Service started")

@app.get("/flights")
def search_flights(origin: str, destination: str, date: Optional[str] = None):
    try:
        resp = flight_client.search_flights(origin, destination, date)
        return {"flights": [{"id": f.id, "flight_number": f.flight_number, "origin": f.origin,
                             "destination": f.destination, "price": f.price, "available_seats": f.available_seats,
                             "status": f.status} for f in resp.flights]}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=503, detail="Flight service unavailable")

@app.get("/flights/{flight_id}")
def get_flight(flight_id: str):
    try:
        resp = flight_client.get_flight(flight_id)
        f = resp.flight
        return {"id": f.id, "flight_number": f.flight_number, "origin": f.origin, "destination": f.destination,
                "price": f.price, "available_seats": f.available_seats, "status": f.status}
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.post("/bookings", response_model=BookingResponse)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    try:
        flight_resp = flight_client.get_flight(data.flight_id)
        flight = flight_resp.flight
        if flight.status != 1:  # SCHEDULED = 1
            raise HTTPException(status_code=400, detail="Flight not available")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=503, detail="Flight service error")
    booking_id = str(uuid.uuid4())
    try:
        reserve_resp = flight_client.reserve_seats(data.flight_id, data.seat_count, booking_id)
        if not reserve_resp.success:
            raise HTTPException(status_code=409, detail="Not enough seats")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise HTTPException(status_code=409, detail="Not enough seats")
        raise HTTPException(status_code=503, detail="Reservation failed")
    total_price = data.seat_count * flight.price
    booking = Booking(
        id=booking_id,
        user_id=data.user_id,
        flight_id=data.flight_id,
        passenger_name=data.passenger_name,
        passenger_email=data.passenger_email,
        seat_count=data.seat_count,
        total_price=total_price,
        status=BookingStatus.CONFIRMED
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking

@app.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail="Booking not confirmed")

    # Release reservation
    try:
        flight_client.release_reservation(booking_id)
    except Exception as e:
        logger.warning(f"Release failed: {e}")

    booking.status = BookingStatus.CANCELLED
    db.commit()
    return {"message": "Cancelled", "id": booking_id}

@app.get("/bookings", response_model=List[BookingResponse])
def list_bookings(user_id: str = Query(...), db: Session = Depends(get_db)):
    bookings = db.query(Booking).filter(Booking.user_id == user_id).all()
    return bookings
