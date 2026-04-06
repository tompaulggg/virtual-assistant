import pytest
from pathlib import Path
from core.types import AssistantConfig, ActionDef, Message


def test_load_config_from_yaml(tmp_path):
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
  name: "TestUser"
  role: "Tester"
  context: "Test context"

permissions:
  allowed_without_asking:
    - reminders
  requires_confirmation:
    - send_email

scheduler:
  morning_briefing: "07:30"
  reminder_check_interval_seconds: 60
""")
    config = AssistantConfig.from_yaml(str(config_file))
    assert config.name == "TestBot"
    assert config.language == "de"
    assert config.model == "claude-sonnet-4-5"
    assert config.max_tokens == 500
    assert config.personality_style == "Freundlich"
    assert config.personality_rules == ["Kurze Antworten"]
    assert config.user_name == "TestUser"
    assert config.user_role == "Tester"
    assert "reminders" in config.allowed_actions
    assert "send_email" in config.confirmation_actions
    assert config.morning_briefing == "07:30"
    assert config.reminder_check_interval == 60


def test_action_def():
    async def dummy_action(data: dict) -> str:
        return "done"

    action = ActionDef(
        name="test_action",
        description="A test action",
        parameters={"text": "string"},
        handler=dummy_action,
    )
    assert action.name == "test_action"
    assert callable(action.handler)


def test_message():
    msg = Message(role="user", content="Hallo")
    assert msg.role == "user"
    assert msg.content == "Hallo"
    assert msg.to_dict() == {"role": "user", "content": "Hallo"}
