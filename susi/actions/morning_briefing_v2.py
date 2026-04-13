"""Combined morning briefing: MC business data + Susi todos/reminders."""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

MC_URL = os.getenv("MISSION_CONTROL_URL", "http://localhost:3000")


async def build_combined_briefing(user_id: str, todo_store, reminder_store, mc_data=None) -> str:
    """Build the full morning briefing combining MC data with personal todos.
    mc_data can be pre-fetched to avoid ACKing the event multiple times.
    """
    lines = ["Guten Morgen Thomas!\n"]

    if mc_data is None:
        mc_data = await _fetch_briefing_event()

    if mc_data:
        # Revenue
        revenue = mc_data.get("revenue", {})
        total = revenue.get("gestern_total", 0)
        change = revenue.get("veraenderung_vs_vorwoche", "N/A")
        if total > 0:
            lines.append(f"Revenue gestern: EUR {total:.2f} ({change})")
            for ch in revenue.get("pro_channel", []):
                lines.append(f"   {ch.get('name', '?')}: EUR {ch.get('revenue', 0):.2f}")
            lines.append("")

        # Wins
        wins = mc_data.get("wins", {})
        small_wins = wins.get("small", [])
        big_wins = wins.get("big", [])
        if small_wins or big_wins:
            lines.append("Wins:")
            for w in big_wins:
                lines.append(f"* {w}")
            for w in small_wins:
                lines.append(f"* {w}")
            lines.append("")

        # Attention
        aufmerksamkeit = mc_data.get("aufmerksamkeit", [])
        if aufmerksamkeit:
            lines.append("Aufmerksamkeit:")
            for a in aufmerksamkeit:
                lines.append(f"* {a}")
            lines.append("")

        # Agent activity
        erledigt = mc_data.get("gestern_erledigt", [])
        if erledigt:
            agent_summary = ", ".join(
                f"{e['agent']} {e['summary'][:40]}" for e in erledigt[:4]
            )
            lines.append(f"Agents gestern: {agent_summary}")

        # Costs
        kosten = mc_data.get("kosten_gestern", 0)
        if kosten:
            lines.append(f"API-Kosten: EUR {kosten:.2f}")
        lines.append("")
    else:
        lines.append(
            "(Mission Control war nicht erreichbar — Business-Update kommt spaeter)\n"
        )

    # Personal todos from Supabase
    todos_text = await todo_store.list_open(user_id)
    if "keine" not in todos_text.lower():
        lines.append("Deine Todos:")
        for todo_line in todos_text.split("\n"):
            stripped = todo_line.strip()
            if stripped and not stripped.startswith("Offene"):
                lines.append(f"* {stripped}")
        lines.append("")

    # Due reminders
    due = await reminder_store.get_due()
    if due:
        lines.append("Erinnerungen:")
        for r in due:
            lines.append(f"* {r['text']}")
        lines.append("")

    # Efficiency tip from MC
    if mc_data:
        tipp = mc_data.get("effizienz_tipp", "")
        if tipp:
            lines.append(f"Tipp: {tipp}")
            lines.append("")

    lines.append("Frag mich wenn du was brauchst!")

    return "\n".join(lines)


async def _fetch_briefing_event() -> dict | None:
    """Fetch and ACK the briefing_ready event from MC."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MC_URL}/api/meta/events/pending")
            if resp.status_code != 200:
                return None

            events = resp.json().get("events", [])
            for event in events:
                if event.get("type") == "briefing_ready":
                    event_id = event.get("id")
                    payload = event.get("payload", {})
                    await client.post(f"{MC_URL}/api/meta/events/{event_id}/ack")
                    return payload

    except httpx.ConnectError:
        logger.warning("MC not reachable for briefing data")
    except Exception as e:
        logger.error(f"Failed to fetch briefing event: {e}")

    return None
