import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from lena.actions.briefing import register, build_morning_briefing


@pytest.fixture
def mock_todo_store():
    store = AsyncMock()
    store.list_open.return_value = "Offene Aufgaben:\n1. Angebot senden (fällig: 2026-04-06)"
    return store


@pytest.fixture
def mock_reminder_store():
    store = AsyncMock()
    store.get_due.return_value = [
        {"text": "Meeting vorbereiten", "remind_at": "2026-04-06T09:00"}
    ]
    return store


@pytest.mark.asyncio
async def test_build_morning_briefing(mock_todo_store, mock_reminder_store):
    briefing = await build_morning_briefing("user1", mock_todo_store, mock_reminder_store)
    assert "Aufgaben" in briefing or "Angebot" in briefing
    assert isinstance(briefing, str)
    assert len(briefing) > 10


def test_register_returns_actions():
    actions = register()
    names = [a["name"] for a in actions]
    assert "briefing" in names
