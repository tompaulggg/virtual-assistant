"""Claudia Bridge — forward channels to Mission Control CEO for CYO analysis."""

import asyncio
import os
import logging
import httpx

logger = logging.getLogger(__name__)

MC_URL = os.getenv("MISSION_CONTROL_URL", "http://localhost:3000")

# Will be set by main.py after bot is created
_telegram_bot = None
_poll_tasks: dict[str, asyncio.Task] = {}


def set_telegram_bot(bot):
    """Set the telegram bot instance for sending async results."""
    global _telegram_bot
    _telegram_bot = bot


def _format_analysis(analysis: dict) -> str:
    """Format CYO analysis result into a readable Telegram message."""
    score = analysis.get("cloning_score", "?")
    confidence = analysis.get("confidence", "?")
    verdict = analysis.get("cloning_verdict", "?")
    red_flags = analysis.get("red_flags", [])
    sprach = analysis.get("sprach_opportunity", {})
    video_ideen = analysis.get("top_5_video_ideen", [])[:3]
    actionplan = analysis.get("actionplan", {})
    kosten = analysis.get("kosten_pro_video", "?")
    stil = analysis.get("empfohlener_stil", "?")

    verdict_icon = {"empfohlen": "Empfohlen", "abgelehnt": "Abgelehnt", "unsicher": "Unsicher"}
    v_text = verdict_icon.get(verdict, verdict)

    lines = [
        "Claudia hat den Channel analysiert:\n",
        f"Score: {score}/10 (Confidence: {confidence})",
        f"Verdict: {v_text}\n",
    ]

    if red_flags:
        lines.append("Red Flags:")
        for flag in red_flags:
            lines.append(f"  - {flag}")
        lines.append("")

    if sprach:
        emp = sprach.get("empfohlene_sprache", "?")
        en = sprach.get("en_konkurrenz", "?")
        it = sprach.get("it_konkurrenz", "?")
        grund = sprach.get("grund", "")
        lines.append(f"Sprache: {emp} empfohlen (EN: {en} Konkurrenten, IT: {it})")
        if grund:
            lines.append(f"  {grund}")
        lines.append("")

    if video_ideen:
        lines.append("Top Video-Ideen:")
        for v in video_ideen:
            rang = v.get("rang", "")
            titel = v.get("titel", "?")
            views = v.get("original_views", "?")
            if isinstance(views, int):
                views = f"{views:,}"
            lines.append(f"  {rang}. \"{titel}\" ({views} Views)")
        lines.append("")

    freq = actionplan.get("frequenz", "?")
    lines.append(f"Action Plan: {freq}, {stil} Stil, {kosten}/Video")

    return "\n".join(lines)


async def _poll_for_result(channel_id: str, channel_name: str, user_id: str):
    """Poll Mission Control for CYO analysis result, then send to user."""
    max_attempts = 12  # 12 x 10s = 2 minutes
    await asyncio.sleep(15)  # give CYO a head start

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{MC_URL}/api/meta/channels")
                if resp.status_code == 200:
                    data = resp.json()
                    channels = data.get("channels", [])
                    for ch in channels:
                        if ch.get("channel_id") == channel_id or ch.get("id") == channel_id:
                            analysis = ch.get("cloning_analysis")
                            if analysis and isinstance(analysis, dict):
                                msg = _format_analysis(analysis)
                                if _telegram_bot:
                                    await _telegram_bot.send_message(
                                        chat_id=user_id, text=msg
                                    )
                                _poll_tasks.pop(channel_id, None)
                                return
        except Exception as e:
            logger.warning(f"Poll attempt {attempt + 1} failed: {e}")

        await asyncio.sleep(10)

    # Timeout — no result after 2 minutes
    if _telegram_bot:
        await _telegram_bot.send_message(
            chat_id=user_id,
            text=f"Claudia braucht länger als erwartet für '{channel_name}'. "
                 f"Frag mich später nochmal mit 'Channel-Status'.",
        )
    _poll_tasks.pop(channel_id, None)


async def _channel_submit(data: dict) -> str:
    """Submit a YouTube channel URL to Claudia. MC resolves the ID and runs CYO."""
    url = data.get("url", "").strip()
    user_id = data.get("user_id", "")

    if not url:
        return "Ich brauch einen YouTube-Link, z.B. youtube.com/@Felunee"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Send URL to MC — MC resolves channel ID via yt-dlp and starts CYO
            resp = await client.post(
                f"{MC_URL}/api/meta/channels/submit-url",
                json={"url": url},
            )

            if resp.status_code != 200:
                error = resp.json().get("error", f"HTTP {resp.status_code}")
                return f"Claudia konnte den Channel nicht verarbeiten: {error}"

            result = resp.json()
            channel_id = result.get("channel_id", "")
            channel_name = result.get("title", url)

            if not channel_id:
                return "Channel wurde gesendet, aber Claudia konnte keine ID ermitteln."

            # Step 2: Start background polling for CYO result
            if channel_id not in _poll_tasks:
                task = asyncio.create_task(
                    _poll_for_result(channel_id, channel_name, user_id)
                )
                _poll_tasks[channel_id] = task

            return (
                f"Hab '{channel_name}' an Claudia weitergeleitet. "
                f"CYO-Analyse läuft — ich meld mich wenn's fertig ist."
            )

    except httpx.ConnectError:
        return (
            "Kann Claudia nicht erreichen — Mission Control scheint offline zu sein. "
            "Läuft der Server auf Port 3000?"
        )
    except Exception as e:
        logger.error(f"Channel submit failed: {e}")
        return f"Fehler beim Weiterleiten: {e}"


async def _channel_status(data: dict) -> str:
    """Get overview of all analyzed channels from Claudia."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MC_URL}/api/meta/channels")

            if resp.status_code != 200:
                return f"Claudia antwortet nicht (HTTP {resp.status_code})"

            data = resp.json()
            channels = data.get("channels", [])

            if not channels:
                return "Noch keine Channels bei Claudia gespeichert."

            lines = ["Channel-Übersicht von Claudia:\n"]
            for ch in channels:
                title = ch.get("title", ch.get("name", "?"))
                status = ch.get("saved_status", "?")
                analysis = ch.get("cloning_analysis")
                score = "—"
                if analysis and isinstance(analysis, dict):
                    score = str(analysis.get("cloning_score", "—"))

                lines.append(f"  {title} — Score: {score}, Status: {status}")

            return "\n".join(lines)

    except httpx.ConnectError:
        return "Kann Claudia nicht erreichen — Mission Control offline?"
    except Exception as e:
        logger.error(f"Channel status failed: {e}")
        return f"Fehler: {e}"


async def _channel_aufbau(data: dict) -> str:
    """Set channel status to 'aufbau' — triggers the build pipeline."""
    channel_name = data.get("channel", "").strip()
    user_id = data.get("user_id", "")

    if not channel_name:
        return "Welchen Channel soll ich in den Aufbau schicken?"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Find the channel by name/title
            resp = await client.get(f"{MC_URL}/api/meta/channels")
            if resp.status_code != 200:
                return "Kann Claudia nicht erreichen."

            channels = resp.json().get("channels", [])
            match = None
            search = channel_name.lower()
            for ch in channels:
                title = (ch.get("title") or ch.get("name") or "").lower()
                handle = (ch.get("handle") or "").lower()
                if search in title or search in handle or title in search:
                    match = ch
                    break

            if not match:
                return f"Kein Channel gefunden der zu '{channel_name}' passt."

            channel_id = match.get("channel_id", match.get("id", ""))
            display_name = match.get("title", match.get("name", channel_name))

            # Set status to aufbau
            status_resp = await client.post(
                f"{MC_URL}/api/meta/channels/{channel_id}/status",
                json={"status": "aufbau"},
            )

            if status_resp.status_code != 200:
                return f"Konnte Status nicht ändern (HTTP {status_resp.status_code})"

            return (
                f"'{display_name}' ist jetzt im Aufbau. "
                f"Claudia startet die Pipeline: Konkurrenz-Analyse, "
                f"Video-Titel, Branding und Bildgenerierung."
            )

    except httpx.ConnectError:
        return "Kann Claudia nicht erreichen — Mission Control offline?"
    except Exception as e:
        logger.error(f"Channel aufbau failed: {e}")
        return f"Fehler: {e}"


ACTIONS = [
    {
        "name": "channel_submit",
        "description": "YouTube-Channel an Claudia (CEO) weiterleiten zur CYO-Analyse. Nutze das wenn Thomas einen YouTube-Link schickt.",
        "parameters": {"url": "string (YouTube Channel URL)"},
        "handler": _channel_submit,
    },
    {
        "name": "channel_status",
        "description": "Übersicht aller Channels und deren Analyse-Status bei Claudia abrufen.",
        "parameters": {},
        "handler": _channel_status,
    },
    {
        "name": "channel_aufbau",
        "description": "Channel in den Aufbau schicken. Nutze das wenn Thomas sagt 'passt', 'mach weiter', 'in den Aufbau', 'starten' nach einer Channel-Analyse.",
        "parameters": {"channel": "string (Channel-Name oder Handle)"},
        "handler": _channel_aufbau,
    },
]


def register() -> list[dict]:
    return ACTIONS
