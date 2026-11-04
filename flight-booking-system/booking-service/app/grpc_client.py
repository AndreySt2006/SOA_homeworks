import grpc
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from .circuit_breaker import circuit_breaker
from . import flight_pb2
from . import flight_pb2_grpc

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GRPC_API_KEY", "secret-flight-key-123")
FLIGHT_HOST = os.getenv("FLIGHT_SERVICE_HOST", "localhost:50051")

def is_retryable(exc):
    if isinstance(exc, grpc.RpcError):
        code = exc.code()
        return code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)
    return False

class FlightClient:
    def __init__(self):
        self.channel = grpc.insecure_channel(FLIGHT_HOST)
        self.stub = flight_pb2_grpc.FlightServiceStub(self.channel)

    def _metadata(self):
        return [("api-key", API_KEY)]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
        retry=retry_if_exception(is_retryable),
        reraise=True
    )
    def _call_with_retry(self, method, request):
        if not circuit_breaker.allow_request():
            raise grpc.RpcError(grpc.StatusCode.UNAVAILABLE, "Circuit breaker OPEN")
        try:
            resp = method(request, metadata=self._metadata(), timeout=5)
            circuit_breaker.record_success()
            return resp
        except Exception as e:
            circuit_breaker.record_failure()
            raise

    def search_flights(self, origin, destination, date=None):
        req = flight_pb2.SearchFlightsRequest(origin=origin, destination=destination, date=date or "")
        return self._call_with_retry(self.stub.SearchFlights, req)

    def get_flight(self, flight_id):
        req = flight_pb2.GetFlightRequest(id=flight_id)
        return self._call_with_retry(self.stub.GetFlight, req)

    def reserve_seats(self, flight_id, seat_count, booking_id):
        req = flight_pb2.ReserveSeatsRequest(flight_id=flight_id, seat_count=seat_count, booking_id=booking_id)
        return self._call_with_retry(self.stub.ReserveSeats, req)

    def release_reservation(self, booking_id):
        req = flight_pb2.ReleaseReservationRequest(booking_id=booking_id)
        return self._call_with_retry(self.stub.ReleaseReservation, req)

flight_client = FlightClient()
