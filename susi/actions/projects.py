"""Projects action — track project status, updates, blockers."""

from core.db import get_supabase


class ProjectStore:
    def __init__(self):
        self.db = get_supabase()

    async def update_status(self, user_id: str, project: str, status: str, notes: str = "") -> str:
        self.db.table("projects").upsert({
            "user_id": user_id,
            "project": project.lower().strip(),
            "status": status,
            "notes": notes,
        }).execute()
        return f"Projekt '{project}' aktualisiert: {status}"

    async def get_all(self, user_id: str) -> str:
        result = (
            self.db.table("projects")
            .select("project, status, notes, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )

        if not result.data:
            return "Keine Projekte getrackt. Sag mir was du gerade baust!"

        lines = ["Deine Projekte:\n"]
        for p in result.data:
            line = f"• **{p['project']}** — {p['status']}"
            if p.get("notes"):
                line += f" ({p['notes']})"
            lines.append(line)
        return "\n".join(lines)

    async def get_blockers(self, user_id: str) -> str:
        result = (
            self.db.table("projects")
            .select("project, status, notes")
            .eq("user_id", user_id)
            .ilike("status", "%block%")
            .execute()
        )

        if not result.data:
            return "Keine Blocker — alles läuft."

        lines = ["Blockierte Projekte:\n"]
        for p in result.data:
            lines.append(f"• {p['project']}: {p['notes'] or p['status']}")
        return "\n".join(lines)


_store = None


def _get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


async def _update(data: dict) -> str:
    return await _get_store().update_status(
        data.get("user_id", ""),
        data["project"],
        data["status"],
        data.get("notes", ""),
    )


async def _list_all(data: dict) -> str:
    return await _get_store().get_all(data.get("user_id", ""))


async def _blockers(data: dict) -> str:
    return await _get_store().get_blockers(data.get("user_id", ""))


ACTIONS = [
    {
        "name": "project_update",
        "description": "Projekt-Status aktualisieren (z.B. 'Tuby Scout fertig', 'AMS blockiert')",
        "parameters": {
            "project": "string (tuby|virtual-assistant|ams|felunee|sonstiges)",
            "status": "string (aktiv|fertig|blockiert|pausiert|nächster-schritt)",
            "notes": "string (optional, Details)",
        },
        "handler": _update,
    },
    {
        "name": "project_list",
        "description": "Alle Projekte und deren Status anzeigen.",
        "parameters": {},
        "handler": _list_all,
    },
    {
        "name": "project_blockers",
        "description": "Zeige nur blockierte Projekte.",
        "parameters": {},
        "handler": _blockers,
    },
]


def register() -> list[dict]:
    return ACTIONS
