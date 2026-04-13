import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import anthropic
from core.types import AssistantConfig, ActionDef
from core.memory import Memory

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).parent.parent / "logs"


class Brain:
    MODEL_COSTS = {
        "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    }

    def __init__(self, config: AssistantConfig):
        self.config = config
        # Use bot-specific API key if available, fall back to default
        key_env = f"{config.name.upper()}_ANTHROPIC_API_KEY"
        api_key = os.getenv(key_env) or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.memory = Memory(bot_name=config.name.lower())
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

    def _build_knowledge_block(self, user_id: str, message: str = "") -> str:
        """Load relevant knowledge via semantic search + recent facts."""
        if not message:
            return self._build_knowledge_block_fallback(user_id)

        # Semantic search for relevant facts
        semantic_results = self.memory.search_knowledge_semantic(user_id, message)
        # Always include recent facts
        recent_results = self.memory.get_recent_knowledge(user_id)

        # If semantic search returned nothing, fall back to old behavior
        if not semantic_results and not recent_results:
            return self._build_knowledge_block_fallback(user_id)

        # Merge and deduplicate by (category, key)
        seen = set()
        merged = []

        for entry in semantic_results:
            ck = (entry["category"], entry["key"])
            if ck not in seen:
                seen.add(ck)
                merged.append(entry)

        for entry in recent_results:
            ck = (entry["category"], entry["key"])
            if ck not in seen:
                seen.add(ck)
                merged.append(entry)

        # Cap at 50
        merged = merged[:50]

        if not merged:
            return ""

        lines = ["", "## Was ich über dich weiß"]
        by_category: dict[str, list[str]] = {}
        for e in merged:
            cat = e["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f"- {e['key']}: {e['value']}")

        for cat, items in by_category.items():
            lines.append(f"\n### {cat.title()}")
            lines.extend(items)

        return "\n".join(lines)

    def _build_knowledge_block_fallback(self, user_id: str) -> str:
        """Fallback: load all knowledge (old behavior, used when no embeddings)."""
        entries = self.memory.get_all_knowledge(user_id, limit=100)
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

    def _build_system_prompt(self, user_id: str, message: str = "") -> str:
        config = self.config
        lines = [
            f"# {config.name}",
            "",
            f"## WICHTIG: Du sprichst mit {config.user_name}. Nur mit {config.user_name}. Niemand anderem.",
            f"Name des Users: {config.user_name}",
            f"Rolle: {config.user_role}",
            f"Kontext: {config.user_context}",
            "",
            "## Kommunikationsstil",
            f"Stil: {config.personality_style}",
            "Regeln:",
        ]
        for rule in config.personality_rules:
            lines.append(f"- {rule}")

        # Inject relevant knowledge — semantic search + recent facts
        knowledge_block = self._build_knowledge_block(user_id, message)
        if knowledge_block:
            lines.append(knowledge_block)
            lines.append("")
            lines.append("WICHTIG: Nutze das gespeicherte Wissen aktiv. Wenn der User etwas fragt das du weißt, bezieh dich darauf. Frag nicht nach Dingen die du schon weißt.")

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

    def _log_cost(self, response, model: str = ""):
        """Log API call cost to JSONL for daily reporting."""
        try:
            usage = response.usage
            model = model or self.config.model
            costs = self.MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
            cost_usd = (
                usage.input_tokens / 1_000_000 * costs["input"]
                + usage.output_tokens / 1_000_000 * costs["output"]
            )
            _LOG_DIR.mkdir(exist_ok=True)
            log_file = _LOG_DIR / f"{self.config.name.lower()}_{datetime.now().strftime('%Y-%m')}.jsonl"
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "bot": self.config.name.lower(),
                "model": model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": round(cost_usd, 6),
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Cost logging failed: {e}")

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

            self._log_cost(extraction, model="claude-haiku-4-5-20251001")
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

    async def process(self, message: str, user_id: str) -> str | dict:
        history = self.memory.get_history(user_id)
        history.append({"role": "user", "content": message})

        max_iterations = 3
        for iteration in range(max_iterations + 1):
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=self._build_system_prompt(user_id, message=message),
                messages=history[-20:],
            )

            self._log_cost(response)
            reply = response.content[0].text.strip()

            # Try to find and execute an action
            action_result = await self._try_execute_action(reply, message, user_id)

            if action_result is None:
                # No action — final text response
                self.memory.save(user_id, message, reply)
                await self._auto_learn(message, reply, user_id)
                return reply

            # Special return type: file to send (don't loop, return immediately)
            if isinstance(action_result, dict) and action_result.get("type") == "send_file":
                self.memory.save(user_id, message, f"[Datei gesendet: {action_result.get('path', '')}]")
                return action_result

            # Action executed — feed result back for follow-up
            if iteration < max_iterations:
                history.append({"role": "assistant", "content": reply})
                history.append({
                    "role": "user",
                    "content": f"[Aktion ausgefuehrt. Ergebnis:]\n{action_result}",
                })
                continue
            else:
                # Max iterations — return last action result
                self.memory.save(user_id, message, str(action_result))
                await self._auto_learn(message, str(action_result), user_id)
                return str(action_result)

        return "Ich konnte die Anfrage nicht vollstaendig bearbeiten."

    async def _try_execute_action(self, reply: str, message: str, user_id: str) -> str | dict | None:
        """Extract and execute action JSON from reply. Returns result or None.
        Does NOT save to memory — caller (process) handles that.
        """
        import re

        json_candidates = []

        # Pattern 1: ```json ... ``` code block
        for m in re.finditer(r'```(?:json)?\s*(\{.*?\})\s*```', reply, re.DOTALL):
            json_candidates.append(m.group(1))

        # Pattern 2: find balanced JSON objects starting with {"action"
        # Use bracket counting instead of regex to handle nested braces
        for start_idx in [m.start() for m in re.finditer(r'\{"action"', reply)]:
            depth = 0
            for i in range(start_idx, len(reply)):
                if reply[i] == '{':
                    depth += 1
                elif reply[i] == '}':
                    depth -= 1
                    if depth == 0:
                        json_candidates.append(reply[start_idx:i+1])
                        break

        # Pattern 3: entire reply is JSON
        if reply.startswith("{"):
            json_candidates.insert(0, reply)

        for candidate in json_candidates:
            try:
                parsed = json.loads(candidate)
                action_name = parsed.get("action")
                if not action_name:
                    continue

                data = parsed.get("data", {})
                action = self.actions.get(action_name)
                if not action:
                    return f"Aktion '{action_name}' ist nicht verfuegbar."

                data["user_id"] = user_id
                result = await action.handler(data)
                self.memory.log_action(user_id, action_name, data)

                # Prepend any text before/after the JSON
                text_parts = reply.replace(candidate, "").strip()
                text_parts = re.sub(r'```json\s*```', '', text_parts).strip()
                if text_parts and isinstance(result, str):
                    return f"{text_parts}\n\n{result}"
                return result
            except (json.JSONDecodeError, KeyError):
                continue

        return None
