"""Todo action — task CRUD with deadlines and priorities."""

import os
from supabase import create_client


class TodoStore:
    def __init__(self):
        self.db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )

    async def add(self, user_id: str, title: str, due_date: str | None = None, priority: str = "normal") -> str:
        row = {
            "user_id": user_id,
            "title": title,
            "priority": priority,
        }
        if due_date:
            row["due_date"] = due_date

        self.db.table("todos").insert(row).execute()

        parts = [f"Aufgabe erstellt: {title}"]
        if due_date:
            parts.append(f"Fällig: {due_date}")
        if priority != "normal":
            parts.append(f"Priorität: {priority}")
        return "\n".join(parts)

    async def list_open(self, user_id: str) -> str:
        result = (
            self.db.table("todos")
            .select("title, due_date, priority")
            .eq("user_id", user_id)
            .eq("status", "open")
            .order("due_date", desc=False)
            .execute()
        )

        if not result.data:
            return "Keine offenen Aufgaben."

        lines = ["Offene Aufgaben:\n"]
        for i, todo in enumerate(result.data, 1):
            line = f"{i}. {todo['title']}"
            if todo.get("due_date"):
                line += f" (fällig: {todo['due_date']})"
            if todo.get("priority") != "normal":
                line += f" [{todo['priority']}]"
            lines.append(line)

        return "\n".join(lines)

    async def complete(self, user_id: str, title_search: str) -> str:
        result = (
            self.db.table("todos")
            .update({"status": "done"})
            .eq("user_id", user_id)
            .eq("status", "open")
            .ilike("title", f"%{title_search}%")
            .execute()
        )

        if result.data:
            return f"Erledigt: {title_search}"
        return f"Keine offene Aufgabe gefunden mit '{title_search}'"


_store = None


def _get_store() -> TodoStore:
    global _store
    if _store is None:
        _store = TodoStore()
    return _store


async def _add(data: dict) -> str:
    return await _get_store().add(
        data.get("user_id", ""),
        data["title"],
        data.get("due_date"),
        data.get("priority", "normal"),
    )


async def _list(data: dict) -> str:
    return await _get_store().list_open(data.get("user_id", ""))


async def _done(data: dict) -> str:
    return await _get_store().complete(
        data.get("user_id", ""),
        data["title"],
    )


ACTIONS = [
    {
        "name": "todo_add",
        "description": "Neue Aufgabe erstellen mit optionaler Deadline und Priorität.",
        "parameters": {"title": "string", "due_date": "string (YYYY-MM-DD, optional)", "priority": "string (high|normal|low, optional)"},
        "handler": _add,
    },
    {
        "name": "todo_list",
        "description": "Alle offenen Aufgaben anzeigen.",
        "parameters": {},
        "handler": _list,
    },
    {
        "name": "todo_done",
        "description": "Aufgabe als erledigt markieren.",
        "parameters": {"title": "string"},
        "handler": _done,
    },
]


def register() -> list[dict]:
    return ACTIONS
