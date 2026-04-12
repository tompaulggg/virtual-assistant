"""Poll Mission Control for events and dispatch to handlers."""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

MC_URL = os.getenv("MISSION_CONTROL_URL", "http://localhost:3000")

# Handlers registered by event_handlers.py
_handlers: dict[str, callable] = {}


def register_handler(event_type: str, handler):
    """Register a handler function for an event type."""
    _handlers[event_type] = handler
    logger.info(f"Event handler registered: {event_type}")


async def poll_and_dispatch(bot_instance, allowed_user_ids: list[str]):
    """Poll MC for pending events, dispatch to handlers, ACK processed events.
    Skips briefing_ready events — those are handled by the dedicated briefing job.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MC_URL}/api/meta/events/pending")
            if resp.status_code != 200:
                return

            events = resp.json().get("events", [])
            if not events:
                return

            for event in events:
                event_type = event.get("type", "")
                event_id = event.get("id")
                payload = event.get("payload", {})

                # Skip briefing — handled by dedicated job
                if event_type == "briefing_ready":
                    continue

                handler = _handlers.get(event_type)
                if handler:
                    try:
                        await handler(bot_instance, allowed_user_ids, event_id, payload)
                    except Exception as e:
                        logger.error(f"Handler error for {event_type}: {e}")
                        continue
                else:
                    logger.warning(f"No handler for event type: {event_type}")

                # ACK the event
                try:
                    await client.post(f"{MC_URL}/api/meta/events/{event_id}/ack")
                except Exception as e:
                    logger.error(f"Failed to ACK event {event_id}: {e}")

    except httpx.ConnectError:
        logger.debug("MC not reachable — skipping poll")
    except Exception as e:
        logger.error(f"Event poll error: {e}")
