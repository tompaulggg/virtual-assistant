"""Reminders action — time-based and recurring reminders."""

import os
from datetime import datetime
from supabase import create_client


class ReminderStore:
    def __init__(self):
        self.db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )

    async def add(self, user_id: str, text: str, when: str, recurring: str | None = None) -> str:
        remind_at = datetime.fromisoformat(when)

        row = {
            "user_id": user_id,
            "text": text,
            "remind_at": remind_at.isoformat(),
        }
        if recurring:
            row["recurring"] = recurring

        self.db.table("reminders").insert(row).execute()

        formatted = remind_at.strftime("%d.%m. um %H:%M Uhr")
        result = f"Erinnerung gesetzt: {text}\nWann: {formatted}"
        if recurring:
            result += f"\nWiederholt sich: wöchentlich" if recurring == "weekly" else f"\nWiederholt sich: {recurring}"
        return result

    async def get_due(self) -> list[dict]:
        now = datetime.now().isoformat()
        result = (
            self.db.table("reminders")
            .select("*")
            .eq("sent", False)
            .lte("remind_at", now)
            .execute()
        )
        return result.data

    async def mark_sent(self, reminder_id: str):
        (
            self.db.table("reminders")
            .update({"sent": True})
            .eq("id", reminder_id)
            .execute()
        )


_store = None


def _get_store() -> ReminderStore:
    global _store
    if _store is None:
        _store = ReminderStore()
    return _store


async def _remind(data: dict) -> str:
    return await _get_store().add(
        data.get("user_id", ""),
        data["text"],
        data["when"],
        data.get("recurring"),
    )


ACTIONS = [
    {
        "name": "remind",
        "description": "Erinnerung setzen. Optional wiederkehrend (daily, weekly, monthly).",
        "parameters": {"text": "string", "when": "string (ISO datetime)", "recurring": "string (daily|weekly|monthly, optional)"},
        "handler": _remind,
    },
]


def register() -> list[dict]:
    return ACTIONS
