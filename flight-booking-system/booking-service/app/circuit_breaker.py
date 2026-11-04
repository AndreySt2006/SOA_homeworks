import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30, window_size: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_size = window_size
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.failures = []  # timestamps

    def _clean_old_failures(self):
        now = time.time()
        self.failures = [t for t in self.failures if now - t < self.window_size]
        self.failure_count = len(self.failures)

    def allow_request(self) -> bool:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit Breaker: OPEN → HALF_OPEN")
                return True
            return False
        return True

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failures = []
            self.failure_count = 0
            logger.info("Circuit Breaker: HALF_OPEN → CLOSED")
        elif self.state == CircuitState.CLOSED:
            self._clean_old_failures()

    def record_failure(self):
        now = time.time()
        self.failures.append(now)
        self.last_failure_time = now
        self._clean_old_failures()
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit Breaker: → OPEN (failures={self.failure_count})")

circuit_breaker = CircuitBreaker()
