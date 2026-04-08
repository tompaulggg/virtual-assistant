"""Knowledge action — store and retrieve facts about people, companies, notes."""

from core.db import get_supabase
from core.memory import Memory
from core.embeddings import embed_text


class KnowledgeStore:
    def __init__(self):
        self.db = get_supabase()
        self.memory = Memory()

    async def store(self, user_id: str, category: str, key: str, value: str) -> str:
        self.memory.store_knowledge(user_id, category, key, value)
        return f"Gemerkt: {key} ({category}) — {value}"

    async def retrieve(self, user_id: str, search: str) -> str:
        # Try semantic search first
        results = self.memory.search_knowledge_semantic(user_id, search)

        if results:
            lines = [f"Gefunden zu '{search}':\n"]
            for entry in results:
                score = entry.get("similarity", 0)
                lines.append(
                    f"[{entry['category']}] {entry['key']}: {entry['value']}"
                    f" ({score:.0%} relevant)"
                )
            return "\n".join(lines)

        # Fallback to ILIKE substring search
        result = (
            self.db.table("knowledge")
            .select("category, key, value")
            .eq("user_id", user_id)
            .ilike("key", f"%{search}%")
            .execute()
        )

        if not result.data:
            result = (
                self.db.table("knowledge")
                .select("category, key, value")
                .eq("user_id", user_id)
                .ilike("value", f"%{search}%")
                .execute()
            )

        if not result.data:
            return f"Keine Einträge gefunden zu '{search}'."

        lines = [f"Gefunden zu '{search}':\n"]
        for entry in result.data:
            lines.append(f"[{entry['category']}] {entry['key']}: {entry['value']}")
        return "\n".join(lines)


_store = None


def _get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


async def _store_fact(data: dict) -> str:
    return await _get_store().store(
        data.get("user_id", ""),
        data.get("category", "notiz"),
        data["key"],
        data["value"],
    )


async def _retrieve(data: dict) -> str:
    return await _get_store().retrieve(
        data.get("user_id", ""),
        data["search"],
    )


ACTIONS = [
    {
        "name": "knowledge_store",
        "description": "Merke dir eine Information: Person, Firma, Kontakt, Notiz.",
        "parameters": {"category": "string (person|firma|notiz)", "key": "string (Name/Titel)", "value": "string (die Info)"},
        "handler": _store_fact,
    },
    {
        "name": "knowledge_retrieve",
        "description": "Suche nach gespeicherten Informationen.",
        "parameters": {"search": "string"},
        "handler": _retrieve,
    },
]


def register() -> list[dict]:
    return ACTIONS
