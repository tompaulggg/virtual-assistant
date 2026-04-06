import pytest
from unittest.mock import MagicMock, patch
from core.memory import Memory


@pytest.fixture
def mock_supabase():
    with patch("core.memory.create_client") as mock_create:
        mock_db = MagicMock()
        mock_create.return_value = mock_db
        yield mock_db


@pytest.fixture
def memory(mock_supabase):
    with patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key",
    }):
        return Memory()


class TestConversations:
    def test_get_history_returns_messages(self, memory, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[
            {"role": "user", "content": "Hallo"},
            {"role": "assistant", "content": "Hi!"},
        ])

        history = memory.get_history("user123", limit=20)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        mock_supabase.table.assert_called_with("conversations")

    def test_save_inserts_two_rows(self, memory, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table

        memory.save("user123", "Hallo", "Hi!")
        mock_table.insert.assert_called_once()
        rows = mock_table.insert.call_args[0][0]
        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[1]["role"] == "assistant"


class TestFacts:
    def test_remember_fact(self, memory, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        memory.remember_fact("user123", "person", "Mueller", "CEO bei Firma XY")
        mock_supabase.table.assert_called_with("facts")
        upsert_data = mock_table.upsert.call_args[0][0]
        assert upsert_data["user_id"] == "user123"
        assert upsert_data["category"] == "person"
        assert upsert_data["key"] == "Mueller"

    def test_recall_facts_with_category(self, memory, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[
            {"category": "person", "key": "Mueller", "value": "CEO"}
        ])

        facts = memory.recall_facts(user_id="user123", category="person")
        assert len(facts) == 1

    def test_recall_facts_filters_by_user_id(self, memory, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        memory.recall_facts(user_id="user123")
        # First .eq() call should be the user_id filter
        first_call = mock_table.eq.call_args_list[0]
        assert first_call[0] == ("user_id", "user123")


class TestAuditLog:
    def test_log_action(self, memory, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table

        memory.log_action("user123", "ghostwrite", {"tone": "formal"})
        mock_supabase.table.assert_called_with("audit_log")
        row = mock_table.insert.call_args[0][0]
        assert row["user_id"] == "user123"
        assert row["action"] == "ghostwrite"
        assert row["details"] == {"tone": "formal"}
