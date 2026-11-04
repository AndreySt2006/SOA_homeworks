import grpc
from concurrent import futures
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from datetime import datetime
from .database import SessionLocal, init_db
from .models import Flight, SeatReservation, FlightStatus, ReservationStatus
from .cache import (
    get_flight_cache, set_flight_cache, invalidate_flight,
    get_search_cache, set_search_cache, invalidate_searches
)
from . import flight_pb2
from . import flight_pb2_grpc
from .auth_interceptor import AuthInterceptor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FlightServicer(flight_pb2_grpc.FlightServiceServicer):
    def _flight_to_proto(self, f: Flight):
        from google.protobuf.timestamp_pb2 import Timestamp
        dep = Timestamp()
        dep.FromDatetime(f.departure_time)
        arr = Timestamp()
        arr.FromDatetime(f.arrival_time)
        status_map = {
            FlightStatus.SCHEDULED: flight_pb2.SCHEDULED,
            FlightStatus.DEPARTED: flight_pb2.DEPARTED,
            FlightStatus.CANCELLED: flight_pb2.CANCELLED,
            FlightStatus.COMPLETED: flight_pb2.COMPLETED,
        }
        return flight_pb2.Flight(
            id=f.id,
            flight_number=f.flight_number,
            airline=f.airline,
            origin=f.origin,
            destination=f.destination,
            departure_time=dep,
            arrival_time=arr,
            total_seats=f.total_seats,
            available_seats=f.available_seats,
            price=f.price,
            status=status_map.get(f.status, flight_pb2.SCHEDULED)
        )

    def SearchFlights(self, request, context):
        date_str = request.date
        cache_key_date = date_str
        cached = get_search_cache(request.origin, request.destination, cache_key_date)
        if cached:
            # Simple reconstruction - only basic fields
            flights = []
            for d in cached:
                f = flight_pb2.Flight(
                    id=d.get("id", ""),
                    flight_number=d.get("flight_number", ""),
                    origin=d.get("origin", ""),
                    destination=d.get("destination", ""),
                    price=d.get("price", 0),
                    available_seats=d.get("available_seats", 0),
                    status=d.get("status", 1)
                )
                flights.append(f)
            return flight_pb2.SearchFlightsResponse(flights=flights)

        db = SessionLocal()
        try:
            query = db.query(Flight).filter(
                Flight.origin == request.origin,
                Flight.destination == request.destination,
                Flight.status == FlightStatus.SCHEDULED
            )
            if date_str:
                from datetime import datetime
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                query = query.filter(Flight.departure_time >= datetime.combine(date, datetime.min.time()),
                                     Flight.departure_time < datetime.combine(date, datetime.max.time()))
            flights = query.all()
            proto_flights = [self._flight_to_proto(f) for f in flights]
            # Cache simple dict
            cache_data = [{"id": f.id, "flight_number": f.flight_number, "origin": f.origin,
                           "destination": f.destination, "price": f.price, "available_seats": f.available_seats,
                           "status": 1} for f in flights]
            set_search_cache(request.origin, request.destination, cache_key_date, cache_data)
            return flight_pb2.SearchFlightsResponse(flights=proto_flights)
        finally:
            db.close()

    def GetFlight(self, request, context):
        cached = get_flight_cache(request.id)
        if cached:
            f = flight_pb2.Flight(
                id=cached.get("id", ""),
                flight_number=cached.get("flight_number", ""),
                airline=cached.get("airline", ""),
                origin=cached.get("origin", ""),
                destination=cached.get("destination", ""),
                total_seats=cached.get("total_seats", 0),
                available_seats=cached.get("available_seats", 0),
                price=cached.get("price", 0),
                status=cached.get("status", 1)
            )
            return flight_pb2.GetFlightResponse(flight=f)

        db = SessionLocal()
        try:
            flight = db.query(Flight).filter(Flight.id == request.id).first()
            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            proto = self._flight_to_proto(flight)
            cache_data = {
                "id": flight.id, "flight_number": flight.flight_number, "airline": flight.airline,
                "origin": flight.origin, "destination": flight.destination,
                "total_seats": flight.total_seats, "available_seats": flight.available_seats,
                "price": flight.price, "status": 1
            }
            set_flight_cache(request.id, cache_data)
            return flight_pb2.GetFlightResponse(flight=proto)
        finally:
            db.close()

    def ReserveSeats(self, request, context):
        db = SessionLocal()
        try:
            # Idempotency: check existing reservation
            existing = db.query(SeatReservation).filter(
                SeatReservation.booking_id == request.booking_id,
                SeatReservation.status == ReservationStatus.ACTIVE
            ).first()
            if existing:
                logger.info(f"Idempotent ReserveSeats for booking {request.booking_id}")
                return flight_pb2.ReserveSeatsResponse(success=True, reservation_id=existing.id)

            # Transaction with SELECT FOR UPDATE
            flight = db.query(Flight).filter(Flight.id == request.flight_id).with_for_update().first()
            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            if flight.available_seats < request.seat_count:
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Not enough seats")

            flight.available_seats -= request.seat_count
            reservation = SeatReservation(
                flight_id=request.flight_id,
                booking_id=request.booking_id,
                seat_count=request.seat_count,
                status=ReservationStatus.ACTIVE
            )
            db.add(reservation)
            db.commit()

            # Invalidate cache
            invalidate_flight(request.flight_id)
            invalidate_searches()

            return flight_pb2.ReserveSeatsResponse(success=True, reservation_id=reservation.id)
        except Exception as e:
            db.rollback()
            logger.error(f"Reserve error: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))
        finally:
            db.close()

    def ReleaseReservation(self, request, context):
        db = SessionLocal()
        try:
            reservation = db.query(SeatReservation).filter(
                SeatReservation.booking_id == request.booking_id,
                SeatReservation.status == ReservationStatus.ACTIVE
            ).first()
            if not reservation:
                return flight_pb2.ReleaseReservationResponse(success=True)  # idempotent

            flight = db.query(Flight).filter(Flight.id == reservation.flight_id).with_for_update().first()
            if flight:
                flight.available_seats += reservation.seat_count
            reservation.status = ReservationStatus.RELEASED
            db.commit()

            invalidate_flight(reservation.flight_id)
            invalidate_searches()

            return flight_pb2.ReleaseReservationResponse(success=True)
        except Exception as e:
            db.rollback()
            context.abort(grpc.StatusCode.INTERNAL, str(e))
        finally:
            db.close()

def serve():
    init_db()
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor()]
    )
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    logger.info("Flight Service gRPC started on 50051")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
