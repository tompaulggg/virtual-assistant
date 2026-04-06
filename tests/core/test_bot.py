import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import time
from core.bot import is_authorized, RateLimiter, sanitize_input


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


class TestSanitizeInput:
    def test_plain_text_unchanged(self):
        assert sanitize_input("Hello World") == "Hello World"

    def test_newlines_preserved(self):
        text = "Line one\nLine two"
        assert sanitize_input(text) == "Line one\nLine two"

    def test_control_characters_removed(self):
        text = "Hello\x00World\x07"
        result = sanitize_input(text)
        assert "\x00" not in result
        assert "\x07" not in result
        assert "Hello" in result
        assert "World" in result

    def test_max_length_enforced(self):
        long_text = "a" * 5000
        result = sanitize_input(long_text, max_length=4000)
        assert len(result) == 4000

    def test_default_max_length_is_4000(self):
        long_text = "b" * 5000
        result = sanitize_input(long_text)
        assert len(result) == 4000

    def test_empty_string(self):
        assert sanitize_input("") == ""
