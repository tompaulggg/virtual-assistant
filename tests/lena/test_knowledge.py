import pytest
from unittest.mock import MagicMock, patch
from lena.actions.knowledge import register, KnowledgeStore


@pytest.fixture
def mock_db():
    with patch("lena.actions.knowledge.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def store(mock_db):
    with patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key",
    }):
        return KnowledgeStore()


class TestKnowledgeStore:
    @pytest.mark.asyncio
    async def test_store_fact(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        result = await store.store("user1", "firma", "TechCorp", "CEO ist Herr Schmidt, Tel 0664123")
        assert "gespeichert" in result.lower() or "gemerkt" in result.lower()

    @pytest.mark.asyncio
    async def test_retrieve_by_key(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.ilike.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[
            {"category": "firma", "key": "TechCorp", "value": "CEO ist Herr Schmidt"}
        ])

        result = await store.retrieve("user1", "TechCorp")
        assert "Schmidt" in result

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, store, mock_db):
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.ilike.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        result = await store.retrieve("user1", "Nonexistent")
        assert "nicht" in result.lower() or "kein" in result.lower()


def test_register_returns_actions():
    actions = register()
    names = [a["name"] for a in actions]
    assert "knowledge_store" in names
    assert "knowledge_retrieve" in names
