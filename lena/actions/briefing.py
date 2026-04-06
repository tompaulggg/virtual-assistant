"""Briefing action — morning briefing and meeting prep."""

from datetime import datetime


async def build_morning_briefing(user_id: str, todo_store, reminder_store) -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    lines = [f"Guten Morgen! Hier dein Briefing für {today}:\n"]

    # Open todos
    todos_text = await todo_store.list_open(user_id)
    if "keine" not in todos_text.lower():
        lines.append(todos_text)
    else:
        lines.append("Keine offenen Aufgaben.")

    # Due reminders
    due = await reminder_store.get_due()
    if due:
        lines.append("\nHeutige Erinnerungen:")
        for r in due:
            lines.append(f"- {r['text']}")
    else:
        lines.append("\nKeine Erinnerungen für heute.")

    return "\n".join(lines)


async def _briefing(data: dict) -> str:
    """On-demand briefing: generates a real briefing using live stores."""
    from lena.actions.reminders import ReminderStore
    from lena.actions.todos import TodoStore

    user_id = data.get("user_id", "")
    todo_store = TodoStore()
    reminder_store = ReminderStore()
    return await build_morning_briefing(user_id, todo_store, reminder_store)


ACTIONS = [
    {
        "name": "briefing",
        "description": "Zeige das aktuelle Briefing: offene Tasks, Erinnerungen, Tagesüberblick.",
        "parameters": {},
        "handler": _briefing,
    },
]


def register() -> list[dict]:
    return ACTIONS
