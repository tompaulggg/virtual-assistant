"""Email sync action — read emails and learn from them."""

from core.email_reader import EmailReader
from core.memory import Memory

_reader = None
_memory = None


def _get_reader():
    global _reader
    if _reader is None:
        _reader = EmailReader()
    return _reader


def _get_memory():
    global _memory
    if _memory is None:
        _memory = Memory(bot_name="susi")
    return _memory


async def _check_emails(data: dict) -> str:
    """On-demand: read recent emails and learn."""
    hours = int(data.get("hours", 12))
    user_id = data.get("user_id", "")
    reader = _get_reader()
    memory = _get_memory()
    return await reader.sync_and_learn(user_id, memory, hours=hours)


async def _email_summary(data: dict) -> str:
    """Get a summary of recent emails without extracting facts."""
    hours = int(data.get("hours", 6))
    reader = _get_reader()
    emails = reader.fetch_recent(hours=hours)

    if not emails:
        return "Keine neuen E-Mails."

    lines = [f"{len(emails)} E-Mails in den letzten {hours}h:\n"]
    for e in emails:
        sender = e["from"].split("<")[0].strip().strip('"')
        lines.append(f"• **{sender}**: {e['subject']}")

    return "\n".join(lines)


ACTIONS = [
    {
        "name": "email_check",
        "description": "E-Mails lesen und daraus lernen (Kontakte, Termine, Abmachungen extrahieren).",
        "parameters": {"hours": "number (optional, default 12 — wie viele Stunden zurück)"},
        "handler": _check_emails,
    },
    {
        "name": "email_summary",
        "description": "Übersicht der neuesten E-Mails (Absender + Betreff).",
        "parameters": {"hours": "number (optional, default 6)"},
        "handler": _email_summary,
    },
]


def register() -> list[dict]:
    return ACTIONS
