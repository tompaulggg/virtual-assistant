"""Handlers for Mission Control events — format messages, send with inline buttons."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def handle_channel_analyzed(bot, user_ids: list[str], event_id: int, payload: dict):
    """Channel was analyzed with score >= 8 — send to Thomas with Aufbau/Kick buttons."""
    name = payload.get("name", "Unknown")
    score = payload.get("score", "?")
    handle = payload.get("handle", "")
    url = payload.get("url", "")
    niche = payload.get("niche", "?")
    confidence = payload.get("confidence", "?")
    subs = payload.get("subscriber_count", 0)
    views = payload.get("avg_views", 0)
    red_flags = payload.get("red_flags", [])

    if isinstance(subs, (int, float)) and subs >= 1000:
        subs_str = f"{subs / 1000:.1f}k"
    else:
        subs_str = str(subs)

    if isinstance(views, (int, float)) and views >= 1000:
        views_str = f"{views / 1000:.1f}k"
    else:
        views_str = str(views)

    link = url or (f"https://youtube.com/{handle}" if handle else "")
    link_line = f"\n{link}" if link else ""

    text = (
        f"Neuer Channel analysiert!\n\n"
        f"{name} (Score {score}/10, {confidence}){link_line}\n"
        f"Nische: {niche}\n"
        f"Subs: {subs_str} | Views: {views_str} avg"
    )

    if red_flags:
        flags_text = ", ".join(str(f) for f in red_flags[:3])
        text += f"\nRed Flags: {flags_text}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Aufbau", callback_data=f"aufbau:{event_id}"),
            InlineKeyboardButton("Kick", callback_data=f"kick:{event_id}"),
        ]
    ])

    # Register event->channel mapping for button callbacks
    from susi.actions.inline_buttons import register_event_channel
    register_event_channel(event_id, payload.get("channel_id", ""))

    for user_id in user_ids:
        if not user_id.strip():
            continue
        try:
            await bot.send_message(chat_id=user_id.strip(), text=text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Failed to send channel alert to {user_id}: {e}")


async def handle_aufbau_review_ready(bot, user_ids: list[str], event_id: int, payload: dict):
    """Aufbau pipeline complete — send review notification with buttons."""
    name = payload.get("name", "Unknown")
    niche = payload.get("niche", "?")
    channel_names = payload.get("channel_names", [])
    has_images = payload.get("has_images", False)

    names_text = ", ".join(channel_names[:3]) if channel_names else "keine generiert"

    text = (
        f"Aufbau fertig fuer {name}!\n\n"
        f"Nische: {niche}\n"
        f"Namensvorschlaege: {names_text}\n"
        f"Bilder: {'Profilbild + Banner generiert' if has_images else 'keine'}\n\n"
        f"Schau dir die Ergebnisse im Dashboard an."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Freigeben", callback_data=f"approve:{event_id}"),
            InlineKeyboardButton("Nachbessern", callback_data=f"revise:{event_id}"),
            InlineKeyboardButton("Kick", callback_data=f"review_kick:{event_id}"),
        ]
    ])

    from susi.actions.inline_buttons import register_event_channel
    register_event_channel(event_id, payload.get("channel_id", ""))

    for user_id in user_ids:
        if not user_id.strip():
            continue
        try:
            await bot.send_message(chat_id=user_id.strip(), text=text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Failed to send aufbau review to {user_id}: {e}")


async def handle_aufbau_started(bot, user_ids: list[str], event_id: int, payload: dict):
    """Confirmation that aufbau pipeline was triggered."""
    name = payload.get("name", "Unknown")

    for user_id in user_ids:
        if not user_id.strip():
            continue
        try:
            await bot.send_message(
                chat_id=user_id.strip(),
                text=f"Pipeline gestartet fuer {name} — ich meld mich wenn's fertig ist.",
            )
        except Exception as e:
            logger.error(f"Failed to send aufbau confirmation: {e}")
