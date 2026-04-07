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

    def _build_knowledge_block(self, user_id: str) -> str:
        """Load all stored knowledge about the user into a prompt section."""
        entries = self.memory.get_all_knowledge(user_id)
        if not entries:
            return ""

        lines = ["", "## Was ich über dich weiß"]
        by_category: dict[str, list[str]] = {}
        for e in entries:
            cat = e["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f"- {e['key']}: {e['value']}")

        for cat, items in by_category.items():
            lines.append(f"\n### {cat.title()}")
            lines.extend(items)

        return "\n".join(lines)

    def _build_system_prompt(self, user_id: str) -> str:
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

        # Inject accumulated knowledge about the user
        knowledge_block = self._build_knowledge_block(user_id)
        if knowledge_block:
            lines.append(knowledge_block)

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

    async def _auto_learn(self, message: str, reply: str, user_id: str):
        """Extract facts from the conversation and store them automatically."""
        try:
            extraction = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=(
                    "Du extrahierst Fakten aus Gesprächen. "
                    "Antworte NUR mit einem JSON-Array von Objekten, oder mit [] wenn nichts Relevantes.\n"
                    "Jedes Objekt: {\"category\": \"...\", \"key\": \"...\", \"value\": \"...\"}\n\n"
                    "Kategorien:\n"
                    "- person (Name, Rolle, Beziehung, Kontaktinfos)\n"
                    "- firma (Firmenname, Branche, Infos)\n"
                    "- termin (wiederkehrende Termine, wichtige Daten)\n"
                    "- vorliebe (Präferenzen, Gewohnheiten, Stil)\n"
                    "- gewohnheit (Arbeitsrhythmus, Routinen)\n"
                    "- kontakt (E-Mail, Telefon, Adresse)\n"
                    "- notiz (alles andere Wichtige)\n\n"
                    "Extrahiere NUR echte Fakten, keine Vermutungen. "
                    "Ignoriere Smalltalk und Floskeln. "
                    "Key = kurzer Bezeichner, Value = die konkrete Info."
                ),
                messages=[{
                    "role": "user",
                    "content": f"User: {message}\nAssistant: {reply}",
                }],
            )

            text = extraction.content[0].text.strip()
            if text.startswith("["):
                facts = json.loads(text)
                for fact in facts:
                    if all(k in fact for k in ("category", "key", "value")):
                        self.memory.store_knowledge(
                            user_id,
                            fact["category"],
                            fact["key"],
                            fact["value"],
                        )
                if facts:
                    logger.info(f"Auto-learned {len(facts)} facts for user {user_id}")
        except Exception as e:
            logger.warning(f"Auto-learn failed: {e}")

    async def process(self, message: str, user_id: str) -> str:
        history = self.memory.get_history(user_id)
        history.append({"role": "user", "content": message})

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self._build_system_prompt(user_id),
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
                # Auto-learn from the exchange
                await self._auto_learn(message, result, user_id)
                return result
            except json.JSONDecodeError:
                pass

        self.memory.save(user_id, message, reply)
        # Auto-learn from the exchange
        await self._auto_learn(message, reply, user_id)
        return reply
