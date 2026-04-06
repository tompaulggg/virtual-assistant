"""Knowledge action — store and retrieve facts about people, companies, notes."""

import os
from supabase import create_client


class KnowledgeStore:
    def __init__(self):
        self.db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )

    async def store(self, user_id: str, category: str, key: str, value: str) -> str:
        self.db.table("knowledge").upsert({
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
        }).execute()
        return f"Gemerkt: {key} ({category}) — {value}"

    async def retrieve(self, user_id: str, search: str) -> str:
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
