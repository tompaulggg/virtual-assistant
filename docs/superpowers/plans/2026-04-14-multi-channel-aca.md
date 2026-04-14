# Multi-Channel ACA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ACA multi-channel-aware so each YouTube channel gets its own ACA instance, managed by the CYO, with gestaffelte production schedules and two-level learnings.

**Architecture:** A channel registry (`aca_channels/`) stores one JSON config per channel. The existing brain.py, topic_ranker, and agents are refactored to accept a channel config parameter instead of running globally. The scheduler reads all active channels and triggers each ACA on its assigned production days. CYO gets new methods to create/manage ACA instances.

**Tech Stack:** Python, existing ACA modules, existing CYO agent, Susi bridge

---

## File Structure

```
~/Documents/BotProjects/
├── meta_memory/
│   └── aca_channels/              # One JSON config per channel
│       ├── aurrraaaaaa.json
│       └── (future channels)
│
├── agents/aca/
│   ├── channel_registry.py        # NEW: CRUD for channel configs
│   ├── brain.py                   # MODIFY: accept channel_config param
│   ├── topic_ranker.py            # MODIFY: filter by niche from config
│   ├── suggestion_generator.py    # MODIFY: pass channel context
│   ├── agents/
│   │   └── performance_analyst.py # MODIFY: filter by channel's videos
│   └── ...
│
├── agents/
│   ├── meta_agents.py             # MODIFY: add CYO ACA management methods
│   └── scheduler.py               # MODIFY: multi-channel scheduling
```

---

### Task 1: Channel Registry

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/channel_registry.py`

- [ ] **Step 1: Create channel_registry.py**

```python
"""
aca/channel_registry.py — Manage ACA channel configurations.

One JSON file per channel in ~/Documents/BotProjects/meta_memory/aca_channels/.
Provides CRUD operations and schedule helpers.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CHANNELS_DIR = Path(__file__).resolve().parent.parent.parent / "meta_memory" / "aca_channels"
CHANNELS_DIR.mkdir(parents=True, exist_ok=True)

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def create_channel(
    channel_id: str,
    handle: str,
    niche: str,
    language: str = "en",
    videos_per_week: int = 3,
    reference_channels: list[str] = None,
    style: str = "",
    youtube_oauth_token: str = "youtube_token.json",
) -> dict:
    """Create a new ACA channel config. Auto-assigns production days."""
    config = {
        "channel_id": channel_id,
        "handle": handle,
        "niche": niche,
        "language": language,
        "production_days": _assign_production_days(videos_per_week),
        "videos_per_week": videos_per_week,
        "reference_channels": reference_channels or [],
        "style": style,
        "status": "analyse",
        "youtube_oauth_token": youtube_oauth_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    config_file = CHANNELS_DIR / f"{handle.lower()}.json"
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    logger.info(f"Channel created: {handle} ({niche}, {language})")
    return config


def get_channel(handle: str) -> dict | None:
    """Load a channel config by handle."""
    config_file = CHANNELS_DIR / f"{handle.lower()}.json"
    if not config_file.exists():
        return None
    return json.loads(config_file.read_text())


def get_all_channels() -> list[dict]:
    """Load all channel configs."""
    channels = []
    for f in sorted(CHANNELS_DIR.glob("*.json")):
        try:
            channels.append(json.loads(f.read_text()))
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
    return channels


def get_active_channels() -> list[dict]:
    """Get channels in 'produktion' or 'live' status."""
    return [ch for ch in get_all_channels() if ch.get("status") in ("produktion", "live")]


def get_channels_for_today() -> list[dict]:
    """Get channels that should produce content today."""
    import calendar
    today = calendar.day_name[datetime.now().weekday()].lower()
    return [ch for ch in get_active_channels() if today in ch.get("production_days", [])]


def update_channel(handle: str, updates: dict) -> dict | None:
    """Update fields in a channel config."""
    config = get_channel(handle)
    if not config:
        return None
    config.update(updates)
    config_file = CHANNELS_DIR / f"{handle.lower()}.json"
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    logger.info(f"Channel updated: {handle} — {list(updates.keys())}")
    return config


def _assign_production_days(videos_per_week: int) -> list[str]:
    """Auto-assign production days, avoiding conflicts with existing channels."""
    existing = get_active_channels()
    day_load = {d: 0 for d in ALL_DAYS}
    for ch in existing:
        for d in ch.get("production_days", []):
            day_load[d] = day_load.get(d, 0) + 1

    # Pick the N least-loaded days
    sorted_days = sorted(day_load.items(), key=lambda x: x[1])
    assigned = [d for d, _ in sorted_days[:videos_per_week]]
    assigned.sort(key=ALL_DAYS.index)
    return assigned
```

- [ ] **Step 2: Create initial config for @Aurrraaaaaa**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.channel_registry import create_channel, get_channel
config = create_channel(
    channel_id='',  # Fill in when known
    handle='Aurrraaaaaa',
    niche='stoicism',
    language='en',
    videos_per_week=3,
    style='dark narration, cinematic',
)
print(f'Created: {config[\"handle\"]} — days: {config[\"production_days\"]}')

# Set to production (already past aufbau)
from aca.channel_registry import update_channel
update_channel('Aurrraaaaaa', {'status': 'produktion'})
loaded = get_channel('Aurrraaaaaa')
print(f'Status: {loaded[\"status\"]}')
"
```

- [ ] **Step 3: Test registry**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.channel_registry import get_all_channels, get_channels_for_today, get_active_channels
all_ch = get_all_channels()
active = get_active_channels()
today = get_channels_for_today()
print(f'All: {len(all_ch)}, Active: {len(active)}, Today: {len(today)}')
for ch in all_ch:
    print(f'  {ch[\"handle\"]}: {ch[\"status\"]} — {ch[\"production_days\"]}')
"
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/channel_registry.py meta_memory/aca_channels/
git commit -m "feat(aca): add channel registry with auto-scheduling"
```

---

### Task 2: Make brain.py channel-aware

**Files:**
- Modify: `~/Documents/BotProjects/agents/aca/brain.py`

The brain currently runs globally. Refactor it to accept an optional channel config, so it filters signals by niche and saves plans per channel.

- [ ] **Step 1: Refactor run_weekly_planning to accept channel config**

Replace the entire content of `~/Documents/BotProjects/agents/aca/brain.py` with:

```python
"""
aca/brain.py — ACA Brain orchestrator.

Weekly cycle per channel:
1. Read signals filtered by channel niche
2. Rank topics with performance feedback
3. Generate content suggestions (Gemini Flash)
4. Send to Thomas via Susi
5. Wait for approval

Supports multi-channel: pass a channel_config dict to run for a specific channel.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aca.topic_ranker import get_top_topics_flat
from aca.suggestion_generator import generate_weekly_plan, format_plan_for_telegram
from aca.susi_bridge import send_to_susi, save_pending_plan
from aca.agents.performance_analyst import get_underperformers, get_all_tracked_videos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [aca-brain] %(levelname)s: %(message)s")
logger = logging.getLogger("aca-brain")


def run_weekly_planning(channel_config: dict = None) -> dict:
    """
    Full weekly planning cycle for one channel (or global if no config).
    """
    niche = channel_config.get("niche", "") if channel_config else ""
    handle = channel_config.get("handle", "global") if channel_config else "global"
    videos = channel_config.get("videos_per_week", 3) if channel_config else 5

    logger.info(f"Starting weekly planning for {handle} (niche: {niche or 'all'})...")

    # Step 1: Get ranked topics, filtered by niche if channel-specific
    topics = get_top_topics_flat(days=7, top_n=30, niche=niche)
    if not topics:
        msg = f"Keine Trend-Signale für {handle} ({niche}) in den letzten 7 Tagen."
        send_to_susi(f"⚠️ ACA [{handle}]: {msg}")
        return {"status": "no_signals", "channel": handle, "message": msg}

    logger.info(f"[{handle}] Got {len(topics)} ranked topics")

    # Step 1b: Build performance context
    perf_context = _build_performance_context(channel_config)

    # Step 2: Generate suggestions
    plan = generate_weekly_plan(topics, performance_context=perf_context, num_youtube=videos)
    yt_count = len(plan.get("youtube", []))
    ig_count = len(plan.get("instagram", []))

    if yt_count == 0 and ig_count == 0:
        msg = f"Konnte keine Content-Vorschläge für {handle} generieren."
        send_to_susi(f"⚠️ ACA [{handle}]: {msg}")
        return {"status": "generation_failed", "channel": handle, "message": msg}

    logger.info(f"[{handle}] Generated plan: {yt_count} YouTube + {ig_count} Instagram")

    # Step 3: Save pending plan (with channel context)
    plan_id = save_pending_plan(plan, channel_handle=handle)

    # Step 4: Send to Thomas via Susi
    header = f"📋 *Wochenplan für @{handle}*\n" if handle != "global" else ""
    telegram_text = header + format_plan_for_telegram(plan)
    sent = send_to_susi(telegram_text)

    return {
        "status": "sent" if sent else "send_failed",
        "channel": handle,
        "plan_id": plan_id,
        "youtube_count": yt_count,
        "instagram_count": ig_count,
        "topics_analyzed": len(topics),
    }


def run_all_channels() -> list[dict]:
    """Run weekly planning for all active channels."""
    from aca.channel_registry import get_active_channels
    channels = get_active_channels()

    if not channels:
        logger.info("No active channels — running global planning")
        return [run_weekly_planning()]

    results = []
    for ch in channels:
        try:
            result = run_weekly_planning(channel_config=ch)
            results.append(result)
        except Exception as e:
            logger.error(f"Planning failed for {ch.get('handle', '?')}: {e}")
            results.append({"status": "error", "channel": ch.get("handle", "?"), "error": str(e)})

    return results


def _build_performance_context(channel_config: dict = None) -> str:
    """Build a text summary of past performance to guide content planning."""
    try:
        videos = get_all_tracked_videos()
        if len(videos) < 2:
            return ""

        videos.sort(key=lambda x: x["views"], reverse=True)
        total = len(videos)
        avg_views = sum(v["views"] for v in videos) // total

        handle = channel_config.get("handle", "") if channel_config else ""
        lines = [f"Performance history ({total} videos, avg {avg_views:,} views):"]

        lines.append("Best performing:")
        for v in videos[:3]:
            lines.append(f"  - {v['video_id']}: {v['views']:,} views")

        lines.append("Worst performing:")
        for v in videos[-3:]:
            lines.append(f"  - {v['video_id']}: {v['views']:,} views")

        underperformers = get_underperformers(threshold_pct=0.5)
        if underperformers:
            lines.append(f"NOTE: {len(underperformers)} videos underperformed. Avoid similar topics/angles.")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Performance context failed: {e}")
        return ""


if __name__ == "__main__":
    results = run_all_channels()
    for r in results:
        print(f"  {r.get('channel', '?')}: {r.get('status')} — {r.get('youtube_count', 0)} YT")
```

- [ ] **Step 2: Update topic_ranker to support niche filter**

In `~/Documents/BotProjects/agents/aca/topic_ranker.py`, modify `get_top_topics_flat` to accept a `niche` param:

Find:
```python
def get_top_topics_flat(days: int = 7, top_n: int = 20) -> list[dict]:
    """Get top N topics across all niches, sorted by score."""
    ranked = rank_topics(days=days, top_n=50)
    flat = []
    for niche, topics in ranked.items():
        for t in topics:
            flat.append({**t, "niche": niche})
    flat.sort(key=lambda x: x["score"], reverse=True)
    return flat[:top_n]
```

Replace with:
```python
def get_top_topics_flat(days: int = 7, top_n: int = 20, niche: str = "") -> list[dict]:
    """Get top N topics, optionally filtered to a specific niche."""
    ranked = rank_topics(days=days, top_n=50)
    flat = []
    for n, topics in ranked.items():
        if niche and n != niche:
            continue
        for t in topics:
            flat.append({**t, "niche": n})
    flat.sort(key=lambda x: x["score"], reverse=True)
    return flat[:top_n]
```

- [ ] **Step 3: Update suggestion_generator to accept num_youtube**

In `~/Documents/BotProjects/agents/aca/suggestion_generator.py`, modify `generate_weekly_plan` signature:

Find:
```python
def generate_weekly_plan(ranked_topics: list[dict], performance_context: str = "") -> dict:
```

Replace with:
```python
def generate_weekly_plan(ranked_topics: list[dict], performance_context: str = "", num_youtube: int = 5) -> dict:
```

And in the prompt, find:
```
1. **5 YouTube video ideas**
```

Replace with:
```
1. **{num_youtube} YouTube video ideas**
```

And find:
```python
        yt = result.get("youtube", [])[:5]
```

Replace with:
```python
        yt = result.get("youtube", [])[:num_youtube]
```

- [ ] **Step 4: Update susi_bridge save_pending_plan to accept channel handle**

In `~/Documents/BotProjects/agents/aca/susi_bridge.py`, modify `save_pending_plan`:

Find:
```python
def save_pending_plan(plan: dict, week: str = "") -> str:
```

Replace with:
```python
def save_pending_plan(plan: dict, week: str = "", channel_handle: str = "") -> str:
```

And find:
```python
    plan_id = f"plan_{week}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
```

Replace with:
```python
    suffix = f"_{channel_handle}" if channel_handle else ""
    plan_id = f"plan_{week}{suffix}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
```

And add `"channel"` to the data dict:
```python
    data = {
        "id": plan_id,
        "week": week,
        "channel": channel_handle,
        "status": "pending",
```

- [ ] **Step 5: Test multi-channel brain**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.channel_registry import get_channel
from aca.brain import run_weekly_planning
config = get_channel('Aurrraaaaaa')
print(f'Testing brain for {config[\"handle\"]} ({config[\"niche\"]})')
# Dry run — no Telegram token set
result = run_weekly_planning(channel_config=config)
print(f'Status: {result[\"status\"]}, Topics: {result.get(\"topics_analyzed\", 0)}')
"
```

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/brain.py agents/aca/topic_ranker.py agents/aca/suggestion_generator.py agents/aca/susi_bridge.py
git commit -m "feat(aca): make brain channel-aware with niche filtering"
```

---

### Task 3: Multi-channel scheduler

**Files:**
- Modify: `~/Documents/BotProjects/agents/scheduler.py`

Replace the single Sunday brain job with a multi-channel aware version, and make daily performance tracking channel-aware.

- [ ] **Step 1: Update scheduler**

In `~/Documents/BotProjects/agents/scheduler.py`:

Replace the brain import:
```python
from aca.brain import run_weekly_planning
```
with:
```python
from aca.brain import run_all_channels
```

Replace the `_run_aca_brain` function and its schedule:
```python
# ── ACA Brain — Weekly Planning ────────────────────────────────────────────
def _run_aca_brain():
    try:
        logger.info("ACA Brain: starting weekly planning")
        result = run_weekly_planning()
        logger.info(f"ACA Brain done: {result.get('status')} — {result.get('youtube_count', 0)} YT + {result.get('instagram_count', 0)} IG")
    except Exception as e:
        logger.error(f"ACA Brain failed: {e}")

schedule.every().sunday.at("20:00").do(_run_aca_brain)
logger.info("ACA Brain scheduled (Sunday 20:00)")
```

with:
```python
# ── ACA Brain — Weekly Planning (all channels) ────────────────────────────
def _run_aca_brain():
    try:
        logger.info("ACA Brain: starting weekly planning for all channels")
        results = run_all_channels()
        for r in results:
            logger.info(f"ACA Brain [{r.get('channel', '?')}]: {r.get('status')} — {r.get('youtube_count', 0)} YT")
    except Exception as e:
        logger.error(f"ACA Brain failed: {e}")

schedule.every().sunday.at("20:00").do(_run_aca_brain)
logger.info("ACA Brain scheduled (Sunday 20:00, all channels)")
```

- [ ] **Step 2: Restart scheduler**

```bash
launchctl kickstart -k gui/$(id -u)/com.tubeclone.scheduler 2>&1
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/scheduler.py
git commit -m "feat(aca): multi-channel scheduler"
```

---

### Task 4: CYO ACA management

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/cyo_manager.py`

CYO creates and manages ACA instances. Called when Thomas says "neuer Channel" to Susi.

- [ ] **Step 1: Create cyo_manager.py**

```python
"""
aca/cyo_manager.py — CYO manages ACA channel instances.

Creates new channels, triggers aufbau, assigns production days.
Called by Susi when Thomas requests a new channel.
"""

import json
import logging
import os
from pathlib import Path

from aca.channel_registry import create_channel, update_channel, get_channel, get_all_channels
from aca.susi_bridge import send_to_susi

logger = logging.getLogger(__name__)


def analyze_niche_for_new_channel(niche: str, language: str = "en") -> dict:
    """
    CYO analyzes a niche for a potential new channel.
    Returns analysis with opportunity score, competition, recommendations.
    """
    import sqlite3
    db_path = Path.home() / "tuby" / "channels.db"
    if not db_path.exists():
        return {"error": "Tuby DB not found"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Count channels in this niche
    rows = conn.execute(
        "SELECT COUNT(*) as cnt, AVG(avg_views) as avg_views, AVG(outlier_score) as avg_outlier "
        "FROM channels WHERE niches LIKE ? AND language = ?",
        (f"%{niche}%", language),
    ).fetchone()

    # Top performers in niche
    top = conn.execute(
        "SELECT title, handle, avg_views, outlier_score, subscriber_count "
        "FROM channels WHERE niches LIKE ? AND language = ? "
        "ORDER BY outlier_score DESC LIMIT 5",
        (f"%{niche}%", language),
    ).fetchall()

    conn.close()

    competition = dict(rows) if rows else {}
    top_channels = [dict(r) for r in top]

    # Simple opportunity score
    channel_count = competition.get("cnt", 0)
    avg_outlier = competition.get("avg_outlier", 0) or 0

    if channel_count < 50:
        opportunity = "hoch"
    elif channel_count < 200:
        opportunity = "mittel"
    else:
        opportunity = "niedrig"

    analysis = {
        "niche": niche,
        "language": language,
        "competition_channels": channel_count,
        "avg_views": int(competition.get("avg_views", 0) or 0),
        "avg_outlier": round(avg_outlier, 1),
        "opportunity": opportunity,
        "top_competitors": top_channels,
        "recommendation": f"{'Gute' if opportunity == 'hoch' else 'Moderate' if opportunity == 'mittel' else 'Schwierige'} Opportunity. "
                         f"{channel_count} Konkurrenten in der DB, avg Outlier {avg_outlier:.1f}x.",
    }

    return analysis


def propose_new_channel(niche: str, language: str = "en") -> str:
    """
    Full flow: analyze niche → format proposal → send to Thomas via Susi.
    Returns the formatted message.
    """
    analysis = analyze_niche_for_new_channel(niche, language)

    top_str = "\n".join(
        f"  • @{ch.get('handle', '?')} — {ch.get('avg_views', 0):,} avg views, {ch.get('outlier_score', 0):.1f}x outlier"
        for ch in analysis.get("top_competitors", [])[:3]
    ) or "  (keine Daten)"

    msg = (
        f"📊 *Nischen-Analyse: {niche} ({language.upper()})*\n\n"
        f"Opportunity: *{analysis['opportunity'].upper()}*\n"
        f"Konkurrenz: {analysis['competition_channels']} Channels in der DB\n"
        f"Avg Views: {analysis['avg_views']:,}\n"
        f"Avg Outlier: {analysis['avg_outlier']}x\n\n"
        f"Top Konkurrenten:\n{top_str}\n\n"
        f"{analysis['recommendation']}\n\n"
        f"Soll ich den Channel aufbauen? Antworte mit 'Ja, starte Aufbau für {niche}'"
    )

    send_to_susi(msg)
    return msg


def start_channel_aufbau(handle: str, niche: str, language: str = "en", style: str = "") -> dict:
    """
    Create ACA config and start aufbau phase.
    Called after Thomas confirms the niche analysis.
    """
    config = create_channel(
        channel_id="",  # Filled in after Thomas creates the YT channel
        handle=handle,
        niche=niche,
        language=language,
        style=style or f"faceless narration, cinematic, {niche}-focused",
    )

    update_channel(handle, {"status": "aufbau"})

    msg = (
        f"🚀 *ACA erstellt für @{handle}*\n\n"
        f"Nische: {niche}\n"
        f"Sprache: {language.upper()}\n"
        f"Produktionstage: {', '.join(config['production_days'])}\n"
        f"Status: Aufbau\n\n"
        f"Nächster Schritt: Channel-Branding wird generiert..."
    )
    send_to_susi(msg)

    return config


def activate_channel(handle: str) -> dict | None:
    """Move channel from aufbau to produktion. Called after Thomas confirms branding."""
    config = update_channel(handle, {"status": "produktion"})
    if config:
        send_to_susi(
            f"✅ *@{handle} ist jetzt in Produktion!*\n"
            f"ACA plant ab Sonntag den ersten Wochenplan.\n"
            f"Produktionstage: {', '.join(config['production_days'])}"
        )
    return config


def get_channels_overview() -> str:
    """Format all channels as a status overview for Susi."""
    channels = get_all_channels()
    if not channels:
        return "Noch keine Channels registriert."

    lines = ["📺 *Channel-Übersicht*\n"]
    for ch in channels:
        status_emoji = {
            "analyse": "🔍",
            "aufbau": "🏗",
            "produktion": "🎬",
            "live": "🟢",
            "paused": "⏸",
        }.get(ch["status"], "❓")

        lines.append(
            f"{status_emoji} *@{ch['handle']}* — {ch['niche']} ({ch['language'].upper()})\n"
            f"   Status: {ch['status']} | Tage: {', '.join(ch.get('production_days', []))}"
        )

    return "\n".join(lines)
```

- [ ] **Step 2: Test CYO manager**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.cyo_manager import analyze_niche_for_new_channel, get_channels_overview

# Test niche analysis
analysis = analyze_niche_for_new_channel('true_crime', 'en')
print(f'Niche: {analysis[\"niche\"]}')
print(f'Competition: {analysis[\"competition_channels\"]} channels')
print(f'Opportunity: {analysis[\"opportunity\"]}')
print(f'Top: {len(analysis[\"top_competitors\"])} competitors')

# Test overview
print()
print(get_channels_overview())
"
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/cyo_manager.py
git commit -m "feat(aca): add CYO manager for channel lifecycle"
```

---

### Task 5: Susi "Neuer Channel" action

**Files:**
- Modify: `~/virtual-assistant/susi/actions/` — add or extend an action that recognizes channel management requests

Since Susi uses Brain's action system (JSON actions in replies), we need to add a channel management action that Susi can trigger.

- [ ] **Step 1: Create channel_management action**

Create `~/virtual-assistant/susi/actions/channel_management.py`:

```python
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

# Add BotProjects agents to path so we can import aca modules
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
```

- [ ] **Step 2: Register the action in Susi main.py**

In `~/virtual-assistant/susi/main.py`, add the import (after existing action imports):

Find:
```python
from susi.actions import projects, ideas, claudia_bridge, email_sync
```

Replace with:
```python
from susi.actions import projects, ideas, claudia_bridge, email_sync, channel_management
```

And add to susi_only list:

Find:
```python
    susi_only = [projects, ideas, claudia_bridge, email_sync]
```

Replace with:
```python
    susi_only = [projects, ideas, claudia_bridge, email_sync, channel_management]
```

- [ ] **Step 3: Test**

```bash
cd ~/virtual-assistant
python3 -c "
from susi.actions.channel_management import register
actions = register()
print(f'Registered {len(actions)} channel actions:')
for a in actions:
    print(f'  - {a[\"name\"]}: {a[\"description\"][:60]}')
"
```

- [ ] **Step 4: Commit + push**

```bash
cd ~/virtual-assistant
git add susi/actions/channel_management.py susi/main.py
git commit -m "feat(susi): add channel management actions (analyze, aufbau, activate, status)"
git push origin master
```

---

### Task 6: Global Learnings

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/global_learnings.py`

CYO aggregates learnings from all ACAs and saves them. Each ACA reads them during topic ranking.

- [ ] **Step 1: Create global_learnings.py**

```python
"""
aca/global_learnings.py — Cross-channel learnings managed by CYO.

CYO aggregates performance patterns from all channels weekly.
ACAs read these learnings to benefit from each other's experience.
"""

import json
import logging
from pathlib import Path

from aca.signals_db import get_all_tracked_videos
from aca.channel_registry import get_active_channels

logger = logging.getLogger(__name__)

LEARNINGS_FILE = Path(__file__).resolve().parent.parent.parent / "meta_memory" / "global_learnings.json"


def aggregate_learnings() -> dict:
    """
    CYO runs this weekly. Extracts patterns across all channels.
    Saves to global_learnings.json.
    """
    videos = get_all_tracked_videos()
    channels = get_active_channels()

    if len(videos) < 5:
        logger.info("Not enough data for global learnings (need 5+ videos)")
        return {}

    # Aggregate by day of week (which upload days perform best)
    # For now: basic stats that grow over time
    total_views = sum(v["views"] for v in videos)
    avg_views = total_views // len(videos)
    top_views = max(v["views"] for v in videos)

    learnings = {
        "total_videos_tracked": len(videos),
        "total_channels": len(channels),
        "avg_views_all_channels": avg_views,
        "top_views": top_views,
        "insights": [],
    }

    # Find what top videos have in common (will get smarter with more data)
    top_videos = sorted(videos, key=lambda x: x["views"], reverse=True)[:5]
    if top_videos:
        learnings["insights"].append(
            f"Top performing videos average {sum(v['views'] for v in top_videos) // len(top_videos):,} views"
        )

    # Save
    LEARNINGS_FILE.write_text(json.dumps(learnings, ensure_ascii=False, indent=2))
    logger.info(f"Global learnings saved: {len(videos)} videos, {len(learnings['insights'])} insights")
    return learnings


def get_learnings() -> dict:
    """Read current global learnings. Returns empty dict if none exist."""
    if not LEARNINGS_FILE.exists():
        return {}
    try:
        return json.loads(LEARNINGS_FILE.read_text())
    except Exception:
        return {}
```

- [ ] **Step 2: Wire to CYO weekly schedule**

In `~/Documents/BotProjects/agents/scheduler.py`, add import:

```python
from aca.global_learnings import aggregate_learnings
```

Add after the performance summary schedule:

```python
# ── ACA Global Learnings (CYO aggregates) ─────────────────────────────────
def _aggregate_global_learnings():
    try:
        logger.info("CYO: aggregating global learnings")
        result = aggregate_learnings()
        logger.info(f"Global learnings: {result.get('total_videos_tracked', 0)} videos, {len(result.get('insights', []))} insights")
    except Exception as e:
        logger.error(f"Global learnings failed: {e}")

schedule.every().sunday.at("19:30").do(_aggregate_global_learnings)
logger.info("Global learnings scheduled (Sunday 19:30, before Brain at 20:00)")
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/global_learnings.py agents/scheduler.py
git commit -m "feat(aca): add global learnings aggregation by CYO"
```

---

### Task 7: End-to-end test + final commit

- [ ] **Step 1: Test full multi-channel flow**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
# Test channel registry
from aca.channel_registry import get_all_channels, get_active_channels, get_channels_for_today
all_ch = get_all_channels()
active = get_active_channels()
today = get_channels_for_today()
print(f'Channels: {len(all_ch)} total, {len(active)} active, {len(today)} producing today')

# Test CYO manager
from aca.cyo_manager import analyze_niche_for_new_channel, get_channels_overview
analysis = analyze_niche_for_new_channel('horror', 'en')
print(f'Horror niche: {analysis[\"opportunity\"]} opportunity, {analysis[\"competition_channels\"]} competitors')

# Test overview
print(get_channels_overview())

# Test global learnings
from aca.global_learnings import get_learnings
learnings = get_learnings()
print(f'Global learnings: {\"exists\" if learnings else \"empty (normal, no data yet)\"}')

print('\nMulti-Channel ACA operational!')
"
```

- [ ] **Step 2: Restart scheduler**

```bash
launchctl kickstart -k gui/$(id -u)/com.tubeclone.scheduler 2>&1
```

- [ ] **Step 3: Final commit**

```bash
cd ~/Documents/BotProjects
git add -A
git commit -m "feat(aca): Multi-Channel ACA complete — registry, CYO manager, global learnings, Susi integration"
```
