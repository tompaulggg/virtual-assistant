"""Handle inline keyboard button callbacks from Telegram."""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx
from telegram import Update, ForceReply
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

MC_URL = os.getenv("MISSION_CONTROL_URL", "http://localhost:3000")

# Maps event_id -> channel_id (populated when events are processed)
event_channel_map: dict[int, str] = {}

# Maps message_id -> channel_id (for ForceReply context)
pending_reviews: dict[int, str] = {}

# Decision log file
DECISIONS_FILE = Path(__file__).resolve().parent.parent / "decisions.jsonl"


def register_event_channel(event_id: int, channel_id: str):
    """Store mapping from event_id to channel_id."""
    event_channel_map[event_id] = channel_id


def _log_decision(channel_id: str, action: str, feedback: str = ""):
    """Append decision to JSONL file for future learning."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "channel_id": channel_id,
        "action": action,
        "feedback": feedback,
    }
    with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if ":" not in data:
        return

    action, event_id_str = data.split(":", 1)
    try:
        event_id = int(event_id_str)
    except ValueError:
        await query.edit_message_text("Ungueltige Aktion.")
        return

    channel_id = event_channel_map.get(event_id)
    if not channel_id:
        await query.edit_message_text(
            query.message.text + "\n\nChannel nicht mehr gefunden — bitte im Dashboard pruefen."
        )
        return

    if action == "aufbau":
        await _handle_aufbau(query, channel_id)
    elif action == "kick":
        await _handle_kick(query, channel_id)
    elif action == "approve":
        await _handle_approve(query, channel_id)
    elif action == "revise":
        await _handle_revise(query, channel_id)
    elif action == "review_kick":
        await _handle_kick(query, channel_id)
    else:
        await query.edit_message_text(f"Unbekannte Aktion: {action}")


async def _handle_aufbau(query, channel_id: str):
    """Trigger aufbau pipeline for a channel."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MC_URL}/api/meta/channels/{channel_id}/aufbau",
                json={},
            )
            if resp.status_code == 200:
                _log_decision(channel_id, "aufbau")
                await query.edit_message_text(
                    query.message.text + "\n\nAufbau gestartet — ich meld mich wenn's fertig ist."
                )
            else:
                await query.edit_message_text(
                    query.message.text
                    + f"\n\nFehler beim Starten (HTTP {resp.status_code}). Versuch's spaeter im Dashboard."
                )
    except httpx.ConnectError:
        await query.edit_message_text(
            query.message.text + "\n\nMission Control nicht erreichbar — versuch's in 5 Minuten."
        )
    except Exception as e:
        logger.error(f"Aufbau trigger failed: {e}")
        await query.edit_message_text(query.message.text + f"\n\nFehler: {e}")


async def _handle_kick(query, channel_id: str):
    """Remove channel from DB."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(f"{MC_URL}/api/meta/channels/{channel_id}")
            if resp.status_code == 200:
                _log_decision(channel_id, "kick")
                await query.edit_message_text(
                    query.message.text + "\n\nChannel entfernt."
                )
            else:
                await query.edit_message_text(
                    query.message.text + f"\n\nFehler beim Loeschen (HTTP {resp.status_code})."
                )
    except Exception as e:
        logger.error(f"Kick failed: {e}")
        await query.edit_message_text(query.message.text + f"\n\nFehler: {e}")


async def _handle_approve(query, channel_id: str):
    """Set channel status to in_motion (production)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{MC_URL}/api/meta/channels/{channel_id}/status",
                json={"status": "in_motion"},
            )
            if resp.status_code == 200:
                _log_decision(channel_id, "approve")
                await query.edit_message_text(
                    query.message.text + "\n\nFreigegeben! Channel geht in Production."
                )
            else:
                await query.edit_message_text(
                    query.message.text + f"\n\nFehler (HTTP {resp.status_code})."
                )
    except Exception as e:
        logger.error(f"Approve failed: {e}")
        await query.edit_message_text(query.message.text + f"\n\nFehler: {e}")


async def _handle_revise(query, channel_id: str):
    """Ask Thomas for revision feedback via ForceReply."""
    msg = await query.message.reply_text(
        "Was soll angepasst werden?",
        reply_markup=ForceReply(selective=True),
    )
    pending_reviews[msg.message_id] = channel_id
    await query.edit_message_text(
        query.message.text + "\n\nNachbessern gewaehlt — schreib dein Feedback."
    )


async def handle_revision_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Thomas' reply to a revision request."""
    reply_to = update.message.reply_to_message
    if not reply_to:
        return

    channel_id = pending_reviews.pop(reply_to.message_id, None)
    if not channel_id:
        return

    feedback = update.message.text
    await update.message.chat.send_action("typing")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MC_URL}/api/meta/channels/{channel_id}/aufbau",
                json={"revisions": feedback},
            )
            if resp.status_code == 200:
                _log_decision(channel_id, "revise", feedback)
                await update.message.reply_text(
                    "Feedback weitergeleitet — Pipeline laeuft nochmal. Ich meld mich wenn's fertig ist."
                )
            else:
                await update.message.reply_text(
                    f"Konnte Feedback nicht weiterleiten (HTTP {resp.status_code}). Versuch's im Dashboard."
                )
    except Exception as e:
        logger.error(f"Revision trigger failed: {e}")
        await update.message.reply_text(f"Fehler: {e}")
