import pytest
from unittest.mock import MagicMock, patch
from lena.actions.todos import register, TodoStore


@pytest.fixture
def mock_db():
    with patch("lena.actions.todos.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def store(mock_db):
    with patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key",
    }):
        return TodoStore()


class TestTodoStore:
    @pytest.mark.asyncio
    async def test_add_todo(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"id": "1"}])

        result = await store.add("user1", "Angebot senden", "2026-04-10", "high")
        assert "Angebot senden" in result
        mock_db.table.assert_called_with("todos")

    @pytest.mark.asyncio
    async def test_list_open(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[
            {"title": "Task 1", "due_date": "2026-04-10", "priority": "high"},
            {"title": "Task 2", "due_date": None, "priority": "normal"},
        ])

        result = await store.list_open("user1")
        assert "Task 1" in result
        assert "Task 2" in result

    @pytest.mark.asyncio
    async def test_list_empty(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        result = await store.list_open("user1")
        assert "keine" in result.lower() or "leer" in result.lower()

    @pytest.mark.asyncio
    async def test_complete_todo(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.ilike.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"id": "1"}])

        result = await store.complete("user1", "Angebot")
        assert "erledigt" in result.lower() or "abgehakt" in result.lower()


def test_register_returns_actions():
    actions = register()
    names = [a["name"] for a in actions]
    assert "todo_add" in names
    assert "todo_list" in names
    assert "todo_done" in names
