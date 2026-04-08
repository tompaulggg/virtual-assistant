import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.brain import Brain
from core.types import AssistantConfig, ActionDef


@pytest.fixture
def config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
assistant:
  name: "TestBot"
  language: "de"
  model: "claude-sonnet-4-5"
  max_tokens: 500

personality:
  style: "Freundlich"
  rules:
    - "Kurze Antworten"

user:
  name: "Tester"
  role: "QA"
  context: "Test context"

permissions:
  allowed_without_asking:
    - test_action
  requires_confirmation:
    - dangerous_action

scheduler:
  morning_briefing: "07:30"
  reminder_check_interval_seconds: 60
""")
    return AssistantConfig.from_yaml(str(config_file))


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.get_history.return_value = []
    mem.save.return_value = None
    mem.log_action.return_value = None
    return mem


@pytest.fixture
def brain(config, mock_memory):
    with patch("core.brain.Memory", return_value=mock_memory):
        b = Brain(config)
        b.memory = mock_memory
        return b


class TestActionRegistration:
    def test_register_action(self, brain):
        async def handler(data):
            return "ok"

        brain.register_action("greet", "Greet someone", {"name": "string"}, handler)
        assert "greet" in brain.actions

    def test_system_prompt_includes_actions(self, brain):
        async def handler(data):
            return "ok"

        brain.register_action("greet", "Greet someone", {"name": "string"}, handler)
        prompt = brain._build_system_prompt("test_user")
        assert "greet" in prompt
        assert "Greet someone" in prompt

    def test_system_prompt_includes_confirmation_actions(self, brain):
        prompt = brain._build_system_prompt("test_user")
        # config fixture has "dangerous_action" in requires_confirmation
        assert "dangerous_action" in prompt
        assert "IMMER" in prompt

    def test_add_prompt_extension(self, brain):
        brain.add_prompt_extension("## Extra\nSome extra instruction")
        prompt = brain._build_system_prompt("test_user")
        assert "Extra" in prompt
        assert "Some extra instruction" in prompt


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_text_response(self, brain):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hallo zurück!")]

        with patch.object(brain.client.messages, "create", return_value=mock_response):
            result = await brain.process("Hallo", "user123")

        assert result == "Hallo zurück!"
        brain.memory.save.assert_called_once_with("user123", "Hallo", "Hallo zurück!")

    @pytest.mark.asyncio
    async def test_action_response(self, brain):
        handler = AsyncMock(return_value="Task erstellt!")
        brain.register_action("todo_add", "Add todo", {"title": "string"}, handler)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='{"action": "todo_add", "data": {"title": "Test Task"}}'
        )]

        with patch.object(brain.client.messages, "create", return_value=mock_response):
            result = await brain.process("Erstell einen Task", "user123")

        # user_id is injected into data before calling the handler
        handler.assert_called_once_with({"title": "Test Task", "user_id": "user123"})
        assert result == "Task erstellt!"
        brain.memory.log_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, brain):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='{"action": "nonexistent", "data": {}}'
        )]

        with patch.object(brain.client.messages, "create", return_value=mock_response):
            result = await brain.process("Do something", "user123")

        assert "unbekannt" in result.lower() or "nicht" in result.lower()
