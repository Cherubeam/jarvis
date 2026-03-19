"""
Global API call rate limiter.

Prevents accidental API DDoS when running multiple concurrent agents.
Uses a simple token bucket algorithm. Thread-safe.
"""

import threading
import time


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Args:
        max_per_minute: Maximum API calls per minute.
        max_per_hour: Maximum API calls per hour (0 = unlimited).
    """

    def __init__(self, max_per_minute: int = 30, max_per_hour: int = 0):
        self._max_per_minute = max_per_minute
        self._max_per_hour = max_per_hour

        # Token bucket for per-minute limiting
        self._tokens = float(max_per_minute)
        self._max_tokens = float(max_per_minute)
        self._refill_rate = max_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()

        # Hourly counter
        self._hour_count = 0
        self._hour_start = time.monotonic()

        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire permission to make an API call.

        Blocks until a token is available or timeout is reached.

        Args:
            timeout: Maximum seconds to wait for a token.

        Returns:
            True if acquired, False if timed out.
        """
        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()

                # Check hourly limit
                if self._max_per_hour > 0:
                    now = time.monotonic()
                    if now - self._hour_start >= 3600:
                        self._hour_count = 0
                        self._hour_start = now
                    if self._hour_count >= self._max_per_hour:
                        if time.monotonic() >= deadline:
                            return False
                        # Wait and retry
                    elif self._tokens >= 1.0:
                        self._tokens -= 1.0
                        self._hour_count += 1
                        return True
                elif self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

            # Wait a bit before retrying
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.1, deadline - time.monotonic()))

    def _refill(self) -> None:
        """Refill tokens based on elapsed time. Must be called with lock held."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        with self._lock:
            self._refill()
            return self._tokens
