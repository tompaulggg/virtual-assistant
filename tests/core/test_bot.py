import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import time
from core.bot import is_authorized, RateLimiter


class TestAuth:
    def test_authorized_user(self):
        assert is_authorized("123", ["123", "456"]) is True

    def test_unauthorized_user(self):
        assert is_authorized("789", ["123", "456"]) is False

    def test_empty_allowlist(self):
        assert is_authorized("123", []) is False


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter(max_per_minute=5)
        for _ in range(5):
            assert limiter.check("user1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_per_minute=2)
        assert limiter.check("user1") is True
        assert limiter.check("user1") is True
        assert limiter.check("user1") is False

    def test_different_users_independent(self):
        limiter = RateLimiter(max_per_minute=1)
        assert limiter.check("user1") is True
        assert limiter.check("user2") is True
        assert limiter.check("user1") is False

    def test_resets_after_window(self):
        limiter = RateLimiter(max_per_minute=1)
        assert limiter.check("user1") is True
        assert limiter.check("user1") is False
        # Simulate time passing
        limiter.requests["user1"] = [time.time() - 61]
        assert limiter.check("user1") is True
