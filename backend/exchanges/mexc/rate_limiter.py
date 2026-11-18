from __future__ import annotations

import threading
import time
from typing import Any


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter for MEXC REST API requests."""

    def __init__(
        self,
        capacity: int = 100,
        refill_per_second: float = 10.0,
        time_fn=time.monotonic,
        sleep_fn=time.sleep,
    ) -> None:
        if capacity <= 0 or refill_per_second <= 0:
            raise ValueError("capacity and refill_per_second must be positive")
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._refill_rate = float(refill_per_second)
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._last_refill = self._time_fn()
        self._backoff_until = 0.0
        self._total_weight_used = 0
        self._lock = threading.Lock()

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self._last_refill)
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now

    def acquire(self, weight: int = 1) -> float:
        """Acquire request weight tokens, sleeping if bucket or backoff requires waiting."""
        if weight <= 0:
            raise ValueError("weight must be positive")
        if weight > self._capacity:
            raise ValueError("weight exceeds bucket capacity")

        total_waited = 0.0
        while True:
            wait_seconds = 0.0
            with self._lock:
                now = self._time_fn()
                self._refill(now)
                if now < self._backoff_until:
                    wait_seconds = self._backoff_until - now
                elif self._tokens >= weight:
                    self._tokens -= weight
                    self._total_weight_used += weight
                    return total_waited
                else:
                    deficit = weight - self._tokens
                    wait_seconds = deficit / self._refill_rate

            if wait_seconds > 0:
                self._sleep_fn(wait_seconds)
                total_waited += wait_seconds

    def trigger_backoff(self, seconds: float) -> None:
        """Pause outbound requests for `seconds` (e.g. after HTTP 429)."""
        with self._lock:
            now = self._time_fn()
            self._backoff_until = max(self._backoff_until, now + max(0.0, seconds))

    def status(self) -> dict[str, Any]:
        """Return current limiter telemetry without leaking credentials."""
        with self._lock:
            now = self._time_fn()
            self._refill(now)
            return {
                "capacity": int(self._capacity),
                "available_tokens": round(self._tokens, 2),
                "refill_per_second": self._refill_rate,
                "total_weight_used": self._total_weight_used,
                "in_backoff": now < self._backoff_until,
            }
