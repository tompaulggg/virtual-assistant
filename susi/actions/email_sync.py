"""Email sync action — read, learn, cleanup, and monitor emails."""

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

    # Classify importance
    emails = reader.classify_importance(emails)

    important = [e for e in emails if e.get("type") == "wichtig"]
    newsletter = [e for e in emails if e.get("type") == "newsletter"]
    spam = [e for e in emails if e.get("type") == "spam"]
    info = [e for e in emails if e.get("type") == "info"]

    lines = [f"{len(emails)} E-Mails in den letzten {hours}h:\n"]

    if important:
        lines.append(f"🔴 **WICHTIG ({len(important)}):**")
        for e in important:
            sender = e["from"].split("<")[0].strip().strip('"')
            lines.append(f"  • {sender}: {e['subject']}")
        lines.append("")

    if info:
        lines.append(f"ℹ️ Info ({len(info)}):")
        for e in info:
            sender = e["from"].split("<")[0].strip().strip('"')
            lines.append(f"  • {sender}: {e['subject']}")
        lines.append("")

    if newsletter or spam:
        lines.append(f"📰 Newsletter/Spam: {len(newsletter) + len(spam)} Stück")

    return "\n".join(lines)


async def _inbox_scan(data: dict) -> str:
    """Scan entire inbox and show top senders by frequency."""
    reader = _get_reader()
    result = reader.scan_inbox(max_emails=500)

    if "error" in result:
        return f"Fehler: {result['error']}"

    lines = [
        f"📧 Postfach-Scan:\n",
        f"Gesamt: {result['total']} E-Mails",
        f"Analysiert: {result['sampled']} (letzte)",
        f"Einzigartige Absender: {result['unique_senders']}\n",
        f"**Top Absender (Newsletter/Spam-Kandidaten):**\n",
    ]

    for addr, count in result["top_senders"][:20]:
        pct = round(count / result["sampled"] * 100)
        lines.append(f"  {count}x ({pct}%) — {addr}")

    lines.append("\n💡 Sag mir welche Absender ich löschen soll, z.B.:")
    lines.append("'Lösch alles von kucoin.com'")

    return "\n".join(lines)


async def _delete_sender(data: dict) -> str:
    """Delete all emails from a specific sender."""
    sender = data.get("sender", "").strip()
    if not sender:
        return "Welchen Absender soll ich löschen? Gib mir die E-Mail-Adresse."

    reader = _get_reader()

    # First find unsubscribe links
    unsub_links = reader.find_unsubscribe_links(sender)

    # Then delete
    count = reader.delete_from_sender(sender)

    lines = [f"🗑️ {count} E-Mails von '{sender}' gelöscht."]

    if unsub_links:
        lines.append(f"\n📭 Abmelde-Links gefunden:")
        for link in unsub_links:
            lines.append(f"  • {link}")
        lines.append("\nKlick einen Link um dich abzumelden.")
    else:
        lines.append("\nKein Abmelde-Link gefunden — die Mails sind trotzdem weg.")

    return "\n".join(lines)


async def _find_unsubscribe(data: dict) -> str:
    """Find unsubscribe links for a sender."""
    sender = data.get("sender", "").strip()
    if not sender:
        return "Welchen Newsletter soll ich abbestellen? Gib mir die E-Mail-Adresse."

    reader = _get_reader()
    links = reader.find_unsubscribe_links(sender)

    if not links:
        return f"Kein Abmelde-Link gefunden für '{sender}'."

    lines = [f"📭 Abmelde-Links für '{sender}':\n"]
    for link in links:
        lines.append(f"• {link}")

    return "\n".join(lines)


ACTIONS = [
    {
        "name": "email_check",
        "description": "E-Mails lesen und daraus lernen (Kontakte, Termine, Abmachungen extrahieren).",
        "parameters": {"hours": "number (optional, default 12)"},
        "handler": _check_emails,
    },
    {
        "name": "email_summary",
        "description": "Übersicht der neuesten E-Mails, sortiert nach Wichtigkeit (wichtig/newsletter/spam).",
        "parameters": {"hours": "number (optional, default 6)"},
        "handler": _email_summary,
    },
    {
        "name": "inbox_scan",
        "description": "Postfach scannen — zeigt Top-Absender und Newsletter-Kandidaten zum Aufräumen.",
        "parameters": {},
        "handler": _inbox_scan,
    },
    {
        "name": "email_delete_sender",
        "description": "Alle E-Mails von einem bestimmten Absender löschen + Abmelde-Link suchen.",
        "parameters": {"sender": "string (E-Mail-Adresse des Absenders)"},
        "handler": _delete_sender,
    },
    {
        "name": "email_unsubscribe",
        "description": "Abmelde-Link für einen Newsletter-Absender finden.",
        "parameters": {"sender": "string (E-Mail-Adresse)"},
        "handler": _find_unsubscribe,
    },
]


def register() -> list[dict]:
    return ACTIONS
