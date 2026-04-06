import pytest
from unittest.mock import MagicMock, patch
from lena.actions.reminders import register, ReminderStore


@pytest.fixture
def mock_db():
    with patch("lena.actions.reminders.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def store(mock_db):
    with patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key",
    }):
        return ReminderStore()


class TestReminderStore:
    @pytest.mark.asyncio
    async def test_add_reminder(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"id": "1"}])

        result = await store.add("user1", "Anruf bei Müller", "2026-04-10T09:00")
        assert "Anruf bei Müller" in result
        assert "10.04" in result

    @pytest.mark.asyncio
    async def test_add_recurring_reminder(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"id": "1"}])

        result = await store.add("user1", "Wochenbericht", "2026-04-07T09:00", "weekly")
        assert "Wochenbericht" in result
        assert "wöchentlich" in result.lower() or "weekly" in result.lower()

    @pytest.mark.asyncio
    async def test_get_due_reminders(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.lte.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[
            {"id": "1", "user_id": "user1", "text": "Meeting!", "remind_at": "2026-04-05T09:00"},
        ])

        due = await store.get_due()
        assert len(due) == 1
        assert due[0]["text"] == "Meeting!"

    @pytest.mark.asyncio
    async def test_mark_sent(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        await store.mark_sent("reminder-id-1")
        mock_table.update.assert_called_once_with({"sent": True})


def test_register_returns_actions():
    actions = register()
    names = [a["name"] for a in actions]
    assert "remind" in names
