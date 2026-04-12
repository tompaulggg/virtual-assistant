"""Calendar action — read Google Calendar events."""

from core.calendar_reader import CalendarReader

_cal = None


def _get_cal():
    global _cal
    if _cal is None:
        _cal = CalendarReader()
    return _cal


async def _today(data: dict) -> str:
    cal = _get_cal()
    events = cal.get_today_events()
    return cal.format_events(events, "📅 Heute:")


async def _tomorrow(data: dict) -> str:
    cal = _get_cal()
    events = cal.get_tomorrow_events()
    return cal.format_events(events, "📅 Morgen:")


async def _week(data: dict) -> str:
    days = int(data.get("days", 7))
    cal = _get_cal()
    events = cal.get_upcoming_events(days=days)
    return cal.format_events(events, f"📅 Nächste {days} Tage:")


ACTIONS = [
    {
        "name": "calendar_today",
        "description": "Zeige alle Termine für heute.",
        "parameters": {},
        "handler": _today,
    },
    {
        "name": "calendar_tomorrow",
        "description": "Zeige alle Termine für morgen.",
        "parameters": {},
        "handler": _tomorrow,
    },
    {
        "name": "calendar_week",
        "description": "Zeige Termine der nächsten Tage/Woche.",
        "parameters": {"days": "number (optional, default 7)"},
        "handler": _week,
    },
]


def register() -> list[dict]:
    return ACTIONS
