"""Unit tests for RateLimiter."""

import pytest
import time

from packages.core.rate_limiter import RateLimiter


@pytest.mark.unit
class TestRateLimiter:

    def test_acquire_within_limit(self):
        limiter = RateLimiter(max_per_minute=10)
        # Should succeed immediately
        assert limiter.acquire(timeout=1.0)

    def test_acquire_multiple(self):
        limiter = RateLimiter(max_per_minute=5)
        for _ in range(5):
            assert limiter.acquire(timeout=0.1)

    def test_acquire_exhausted_waits(self):
        limiter = RateLimiter(max_per_minute=1)
        # First should succeed
        assert limiter.acquire(timeout=0.1)
        # Second should fail quickly (not enough tokens, short timeout)
        assert not limiter.acquire(timeout=0.2)

    def test_tokens_refill(self):
        limiter = RateLimiter(max_per_minute=60)  # 1 per second
        assert limiter.acquire(timeout=0.1)
        # After 1 second, should have 1 more token
        time.sleep(1.1)
        assert limiter.acquire(timeout=0.1)

    def test_available_tokens(self):
        limiter = RateLimiter(max_per_minute=10)
        initial = limiter.available_tokens
        assert initial == pytest.approx(10.0, abs=0.5)
        limiter.acquire(timeout=0.1)
        assert limiter.available_tokens < initial
