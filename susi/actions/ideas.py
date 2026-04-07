"""Ideas action — capture, list, and prioritize ideas."""

import os
from supabase import create_client


class IdeaStore:
    def __init__(self):
        self.db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )

    async def capture(self, user_id: str, idea: str, project: str = "") -> str:
        self.db.table("ideas").insert({
            "user_id": user_id,
            "idea": idea,
            "project": project.lower().strip() if project else "allgemein",
            "status": "neu",
        }).execute()
        return f"Idee gespeichert: {idea}"

    async def list_ideas(self, user_id: str, project: str = "") -> str:
        query = (
            self.db.table("ideas")
            .select("idea, project, status, created_at")
            .eq("user_id", user_id)
            .eq("status", "neu")
            .order("created_at", desc=True)
            .limit(20)
        )
        if project:
            query = query.eq("project", project.lower().strip())

        result = query.execute()

        if not result.data:
            return "Keine offenen Ideen. Ruhig im Kopf — oder einfach noch nichts gesagt?"

        lines = ["Deine Ideen:\n"]
        for i in result.data:
            lines.append(f"• [{i['project']}] {i['idea']}")
        return "\n".join(lines)

    async def promote(self, user_id: str, search: str) -> str:
        result = (
            self.db.table("ideas")
            .select("id, idea")
            .eq("user_id", user_id)
            .eq("status", "neu")
            .ilike("idea", f"%{search}%")
            .limit(1)
            .execute()
        )

        if not result.data:
            return f"Keine Idee gefunden zu '{search}'."

        idea = result.data[0]
        self.db.table("ideas").update({"status": "priorisiert"}).eq("id", idea["id"]).execute()
        return f"Idee priorisiert: {idea['idea']}"


_store = None


def _get_store() -> IdeaStore:
    global _store
    if _store is None:
        _store = IdeaStore()
    return _store


async def _capture(data: dict) -> str:
    return await _get_store().capture(
        data.get("user_id", ""),
        data["idea"],
        data.get("project", ""),
    )


async def _list(data: dict) -> str:
    return await _get_store().list_ideas(
        data.get("user_id", ""),
        data.get("project", ""),
    )


async def _promote(data: dict) -> str:
    return await _get_store().promote(
        data.get("user_id", ""),
        data["search"],
    )


ACTIONS = [
    {
        "name": "idea_capture",
        "description": "Neue Idee speichern — Feature, Projekt, Business-Idee, egal was.",
        "parameters": {
            "idea": "string (die Idee)",
            "project": "string (optional: tuby|virtual-assistant|ams|felunee)",
        },
        "handler": _capture,
    },
    {
        "name": "idea_list",
        "description": "Offene Ideen anzeigen, optional gefiltert nach Projekt.",
        "parameters": {"project": "string (optional)"},
        "handler": _list,
    },
    {
        "name": "idea_promote",
        "description": "Eine Idee als priorisiert markieren.",
        "parameters": {"search": "string (Suchbegriff)"},
        "handler": _promote,
    },
]


def register() -> list[dict]:
    return ACTIONS
