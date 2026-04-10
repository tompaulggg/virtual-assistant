"""
susi/actions/cost_tracker.py — Daily cost tracking and alerts.

Reads JSONL cost logs from:
- ~/virtual-assistant/logs/ (Susi + Lena)
- ~/Documents/BotProjects/meta_logs/ (MC agents)

Fixed subscriptions are hardcoded and shown in monthly summaries.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Log directories
VA_LOGS = Path(__file__).resolve().parent.parent.parent / "logs"
MC_LOGS = Path.home() / "Documents" / "BotProjects" / "meta_logs"

# Monthly subscriptions (EUR)
SUBSCRIPTIONS = {
    "Claude Pro": 90.0,
    "ElevenLabs": 22.0,
    "ChatGPT Plus": 20.0,
}

# Alert threshold: warn if daily API cost exceeds this (USD)
DAILY_ALERT_THRESHOLD = 5.0


def _read_jsonl_costs(log_dir: Path, date_str: str, month_str: str) -> list[dict]:
    """Read all JSONL entries for a given date from all log files for the month."""
    entries = []
    if not log_dir.exists():
        return entries
    for f in log_dir.glob(f"*_{month_str}.jsonl"):
        try:
            for line in open(f, "r"):
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if ts.startswith(date_str):
                    entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
    return entries


def _read_month_costs(log_dir: Path, month_str: str) -> list[dict]:
    """Read all JSONL entries for the entire month."""
    entries = []
    if not log_dir.exists():
        return entries
    for f in log_dir.glob(f"*_{month_str}.jsonl"):
        try:
            for line in open(f, "r"):
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
    return entries


def _group_by_source(entries: list[dict]) -> dict[str, float]:
    """Group entries by bot/agent name and sum costs."""
    groups = {}
    for e in entries:
        name = e.get("bot") or e.get("agent") or "unknown"
        groups[name] = groups.get(name, 0) + e.get("cost_usd", 0)
    return groups


def get_daily_summary() -> str:
    """Build the daily cost summary message."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")
    day_of_month = now.day

    # Collect today's costs
    va_today = _read_jsonl_costs(VA_LOGS, date_str, month_str)
    mc_today = _read_jsonl_costs(MC_LOGS, date_str, month_str)

    all_groups = _group_by_source(va_today + mc_today)
    today_total = sum(all_groups.values())

    # Collect month-to-date costs
    va_month = _read_month_costs(VA_LOGS, month_str)
    mc_month = _read_month_costs(MC_LOGS, month_str)
    month_total_api = sum(e.get("cost_usd", 0) for e in va_month + mc_month)

    # Format message
    lines = [f"📊 Kosten {now.strftime('%d.%m.%Y')}", ""]

    # Today's API costs by source
    lines.append("API heute:")
    if all_groups:
        for name, cost in sorted(all_groups.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: ${cost:.2f}")
        lines.append(f"  Gesamt: ${today_total:.2f}")
    else:
        lines.append("  Keine API-Kosten heute")

    lines.append("")

    # Month-to-date
    sub_monthly = sum(SUBSCRIPTIONS.values())
    sub_mtd = round(sub_monthly / 30 * day_of_month, 2)

    lines.append(f"Monat bisher (Tag {day_of_month}):")
    lines.append(f"  API: ${month_total_api:.2f}")
    lines.append(f"  Subscriptions: ~€{sub_mtd:.0f}")
    lines.append(f"  Hochrechnung Monat: ~€{round((month_total_api + sub_mtd) / day_of_month * 30)}")

    # Alert
    if today_total > DAILY_ALERT_THRESHOLD:
        lines.append("")
        lines.append(f"⚠️ Tageskosten über ${DAILY_ALERT_THRESHOLD:.0f}! Prüfe ob was ungewöhnlich läuft.")

    return "\n".join(lines)


def is_cost_alert() -> tuple[bool, str]:
    """Check if current costs warrant an immediate alert."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    va_today = _read_jsonl_costs(VA_LOGS, date_str, month_str)
    mc_today = _read_jsonl_costs(MC_LOGS, date_str, month_str)

    today_total = sum(e.get("cost_usd", 0) for e in va_today + mc_today)

    if today_total > DAILY_ALERT_THRESHOLD:
        groups = _group_by_source(va_today + mc_today)
        top = max(groups.items(), key=lambda x: x[1])
        return True, (
            f"⚠️ Kosten-Alarm: ${today_total:.2f} heute!\n"
            f"Größter Posten: {top[0]} (${top[1]:.2f})\n"
            f"Prüfe ob alles normal läuft."
        )
    return False, ""
