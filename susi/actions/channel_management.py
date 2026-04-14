"""
susi/actions/channel_management.py — Channel management via ACA/CYO.

Susi triggers this when Thomas asks about channels:
- "Neuer Channel für True Crime"
- "Channel-Status"
- "Starte Aufbau für @handle"
- "Produktion starten für @handle"
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "BotProjects" / "agents"))

logger = logging.getLogger(__name__)


def register() -> list[dict]:
    return [
        {
            "name": "channel_analyze",
            "description": "Analysiere eine Nische für einen neuen YouTube-Channel. Nutze dies wenn Thomas einen neuen Channel starten will.",
            "parameters": {
                "niche": "Name der Nische (z.B. 'true crime', 'stoicism', 'finance')",
                "language": "Sprache des Channels: 'en', 'de', 'it' (default: 'en')",
            },
            "handler": handle_analyze,
        },
        {
            "name": "channel_aufbau",
            "description": "Starte den Aufbau eines neuen Channels. Thomas muss vorher die Nischen-Analyse bestätigt haben.",
            "parameters": {
                "handle": "YouTube Handle/Name für den neuen Channel",
                "niche": "Nische des Channels",
                "language": "Sprache (default: 'en')",
            },
            "handler": handle_aufbau,
        },
        {
            "name": "channel_activate",
            "description": "Aktiviere einen Channel für die Produktion. Aufbau muss abgeschlossen sein.",
            "parameters": {
                "handle": "YouTube Handle des Channels",
            },
            "handler": handle_activate,
        },
        {
            "name": "channel_status",
            "description": "Zeige den Status aller registrierten Channels.",
            "parameters": {},
            "handler": handle_status,
        },
    ]


async def handle_analyze(data: dict) -> str:
    from aca.cyo_manager import propose_new_channel
    niche = data.get("niche", "")
    language = data.get("language", "en")
    if not niche:
        return "Welche Nische soll ich analysieren?"
    propose_new_channel(niche, language)
    return f"Nischen-Analyse für '{niche}' ({language.upper()}) wird erstellt..."


async def handle_aufbau(data: dict) -> str:
    from aca.cyo_manager import start_channel_aufbau
    handle = data.get("handle", "")
    niche = data.get("niche", "")
    language = data.get("language", "en")
    if not handle or not niche:
        return "Ich brauche einen Handle und eine Nische für den Aufbau."
    start_channel_aufbau(handle, niche, language)
    return f"Aufbau für @{handle} gestartet!"


async def handle_activate(data: dict) -> str:
    from aca.cyo_manager import activate_channel
    handle = data.get("handle", "")
    if not handle:
        return "Welchen Channel soll ich aktivieren?"
    result = activate_channel(handle)
    if result:
        return f"@{handle} ist jetzt in Produktion!"
    return f"Channel @{handle} nicht gefunden."


async def handle_status(data: dict) -> str:
    from aca.cyo_manager import get_channels_overview
    return get_channels_overview()
