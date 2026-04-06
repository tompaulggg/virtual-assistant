import json
import logging
import anthropic
from core.types import AssistantConfig, ActionDef
from core.memory import Memory

logger = logging.getLogger(__name__)


class Brain:
    def __init__(self, config: AssistantConfig):
        self.config = config
        self.client = anthropic.Anthropic()
        self.memory = Memory()
        self.actions: dict[str, ActionDef] = {}
        self.prompt_extensions: list[str] = []

    def add_prompt_extension(self, text: str):
        """Append extra instructions to the system prompt (e.g. from action modules)."""
        self.prompt_extensions.append(text)

    def register_action(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler,
    ):
        self.actions[name] = ActionDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def _build_system_prompt(self) -> str:
        config = self.config
        lines = [
            f"# {config.name} — Persönliche Assistentin",
            "",
            f"## Über {config.user_name}",
            f"Rolle: {config.user_role}",
            f"Kontext: {config.user_context}",
            "",
            f"## Kommunikationsstil",
            f"Stil: {config.personality_style}",
            "Regeln:",
        ]
        for rule in config.personality_rules:
            lines.append(f"- {rule}")

        if self.actions:
            lines.append("")
            lines.append("## Verfügbare Aktionen")
            lines.append("Wenn du eine Aktion ausführen willst, antworte NUR mit validem JSON:")
            lines.append("")
            for action in self.actions.values():
                params_str = json.dumps(action.parameters, ensure_ascii=False)
                lines.append(
                    f'{{"action": "{action.name}", "data": {params_str}}}'
                    f"  — {action.description}"
                )
            lines.append("")
            lines.append("Für normale Textantworten: einfach Text, kein JSON.")

        if config.confirmation_actions:
            lines.append("")
            lines.append("## Bestätigungspflichtige Aktionen")
            confirmation_list = ", ".join(config.confirmation_actions)
            lines.append(
                f"Für diese Aktionen IMMER zuerst den User fragen, bevor du sie ausführst: {confirmation_list}"
            )

        for extension in self.prompt_extensions:
            lines.append(extension)

        return "\n".join(lines)

    async def process(self, message: str, user_id: str) -> str:
        history = self.memory.get_history(user_id)
        history.append({"role": "user", "content": message})

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self._build_system_prompt(),
            messages=history[-20:],
        )

        reply = response.content[0].text.strip()

        if reply.startswith("{"):
            try:
                parsed = json.loads(reply)
                action_name = parsed.get("action")
                data = parsed.get("data", {})

                action = self.actions.get(action_name)
                if not action:
                    result = f"Aktion '{action_name}' ist nicht verfügbar."
                    self.memory.save(user_id, message, result)
                    return result

                # Inject user_id so all handlers have access to it
                data["user_id"] = user_id
                result = await action.handler(data)
                self.memory.log_action(user_id, action_name, data)
                self.memory.save(user_id, message, result)
                return result
            except json.JSONDecodeError:
                pass

        self.memory.save(user_id, message, reply)
        return reply
