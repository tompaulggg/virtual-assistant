from dataclasses import dataclass, field
from typing import Callable, Awaitable
import yaml


@dataclass
class Message:
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ActionDef:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], Awaitable[str]]


@dataclass
class AssistantConfig:
    name: str
    language: str
    model: str
    max_tokens: int
    personality_style: str
    personality_rules: list[str]
    user_name: str
    user_role: str
    user_context: str
    allowed_actions: list[str]
    confirmation_actions: list[str]
    morning_briefing: str
    reminder_check_interval: int

    @classmethod
    def from_yaml(cls, path: str) -> "AssistantConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        assistant = data["assistant"]
        personality = data["personality"]
        user = data["user"]
        permissions = data["permissions"]
        scheduler = data["scheduler"]

        return cls(
            name=assistant["name"],
            language=assistant["language"],
            model=assistant["model"],
            max_tokens=assistant["max_tokens"],
            personality_style=personality["style"],
            personality_rules=personality["rules"],
            user_name=user["name"],
            user_role=user["role"],
            user_context=user["context"],
            allowed_actions=permissions["allowed_without_asking"],
            confirmation_actions=permissions["requires_confirmation"],
            morning_briefing=scheduler["morning_briefing"],
            reminder_check_interval=scheduler["reminder_check_interval_seconds"],
        )
