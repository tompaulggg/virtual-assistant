# ACA Phase 2: Brain (Topic Ranking + Susi Integration) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ACA Brain that reads sensing signals, ranks topics, generates weekly content suggestions, and presents them to Thomas via Susi with approval flow.

**Architecture:** New modules in `aca/`: a topic ranker (Gemini Flash), a suggestion generator (Haiku), and a Susi bridge that sends formatted plans and listens for approvals. A cron job triggers the weekly planning cycle on Sunday 20:00.

**Tech Stack:** Python, google-genai (Gemini Flash), anthropic (Haiku), Susi Telegram integration

---

## File Structure

```
~/Documents/BotProjects/agents/aca/
├── (existing) signals_db.py, collectors...
├── topic_ranker.py        # Reads signals, deduplicates, scores → ranked topic list
├── suggestion_generator.py # Haiku generates formatted weekly plan from ranked topics
├── susi_bridge.py          # Sends plans to Susi via Telegram, handles approvals
└── brain.py                # Orchestrates the weekly cycle
```

**Modify:**
- `~/Documents/BotProjects/agents/scheduler.py` — add weekly brain cron
- `~/Documents/BotProjects/.env` — add GEMINI_API_KEY
- `~/virtual-assistant/susi/main.py` — add ACA approval handler

---

### Task 1: Add Gemini key to BotProjects

**Files:**
- Modify: `~/Documents/BotProjects/.env`

- [ ] **Step 1: Copy Gemini key from Tuby**

```bash
GEMINI_KEY=$(grep GEMINI_API_KEY /Users/admin/tuby/.env | cut -d= -f2)
echo "" >> /Users/admin/Documents/BotProjects/.env
echo "# Gemini Flash (shared with Tuby, for ACA topic ranking)" >> /Users/admin/Documents/BotProjects/.env
echo "GEMINI_API_KEY=$GEMINI_KEY" >> /Users/admin/Documents/BotProjects/.env
```

- [ ] **Step 2: Verify**

```bash
grep GEMINI_API_KEY /Users/admin/Documents/BotProjects/.env | head -1
```

Expected: `GEMINI_API_KEY=AIzaSy...`

---

### Task 2: Topic Ranker

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/topic_ranker.py`

Reads last 7 days of signals, deduplicates similar topics, aggregates scores across sources, returns top N topics per niche.

- [ ] **Step 1: Create topic_ranker.py**

```python
"""
aca/topic_ranker.py — Rank topics from collected signals.

Reads signals, deduplicates, aggregates scores across sources,
returns top topics per niche. No LLM needed for basic ranking.
"""

import logging
from collections import defaultdict

from aca.signals_db import get_signals

logger = logging.getLogger(__name__)


def rank_topics(days: int = 7, top_n: int = 10) -> dict[str, list[dict]]:
    """
    Rank topics across all sources for each niche.
    Returns {niche: [{topic, score, sources, source_count}]}.
    """
    signals = get_signals(days=days)
    if not signals:
        logger.warning("No signals found in the last %d days", days)
        return {}

    # Aggregate by niche → normalized topic
    niche_topics = defaultdict(lambda: defaultdict(lambda: {
        "score": 0.0,
        "sources": set(),
        "count": 0,
        "best_raw": {},
    }))

    for sig in signals:
        niche = sig["niche"]
        topic = _normalize(sig["topic"])
        if not topic or len(topic) < 5:
            continue

        entry = niche_topics[niche][topic]
        entry["score"] += sig["score"]
        entry["sources"].add(sig["source"])
        entry["count"] += 1
        # Keep the raw_data from the highest-scoring signal
        if sig["score"] >= entry.get("best_score", 0):
            entry["best_score"] = sig["score"]
            import json
            raw = sig.get("raw_data", "{}")
            entry["best_raw"] = json.loads(raw) if isinstance(raw, str) else raw

    # Build ranked lists per niche
    result = {}
    for niche, topics in niche_topics.items():
        ranked = []
        for topic, data in topics.items():
            # Boost score for topics appearing in multiple sources
            source_boost = len(data["sources"]) * 10
            final_score = data["score"] + source_boost

            ranked.append({
                "topic": topic,
                "score": round(final_score, 1),
                "sources": sorted(data["sources"]),
                "source_count": len(data["sources"]),
                "signal_count": data["count"],
                "raw_data": data["best_raw"],
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        result[niche] = ranked[:top_n]

    logger.info(
        "Ranked topics: %s",
        ", ".join(f"{n}: {len(t)}" for n, t in result.items()),
    )
    return result


def get_top_topics_flat(days: int = 7, top_n: int = 20) -> list[dict]:
    """
    Get top N topics across all niches, sorted by score.
    Each entry includes the niche.
    """
    ranked = rank_topics(days=days, top_n=50)
    flat = []
    for niche, topics in ranked.items():
        for t in topics:
            flat.append({**t, "niche": niche})
    flat.sort(key=lambda x: x["score"], reverse=True)
    return flat[:top_n]


def _normalize(text: str) -> str:
    """Normalize topic text for deduplication."""
    return text.strip().lower()[:200]
```

- [ ] **Step 2: Test topic ranker**

```bash
cd /Users/admin/Documents/BotProjects/agents
python3 -c "
from aca.topic_ranker import rank_topics, get_top_topics_flat
ranked = rank_topics(days=7, top_n=5)
for niche, topics in list(ranked.items())[:3]:
    print(f'\n{niche}:')
    for t in topics[:3]:
        print(f'  {t[\"score\"]:6.1f} | {t[\"sources\"]} | {t[\"topic\"][:60]}')
print(f'\nTop 5 flat:')
for t in get_top_topics_flat(days=7, top_n=5):
    print(f'  {t[\"score\"]:6.1f} | {t[\"niche\"]:12s} | {t[\"topic\"][:50]}')
"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/admin/Documents/BotProjects
git add agents/aca/topic_ranker.py
git commit -m "feat(aca): add topic ranker"
```

---

### Task 3: Suggestion Generator

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/suggestion_generator.py`

Takes ranked topics and uses Gemini Flash to generate 5 YouTube video ideas + 7 Instagram post ideas as a structured weekly plan.

- [ ] **Step 1: Create suggestion_generator.py**

```python
"""
aca/suggestion_generator.py — Generate weekly content suggestions.

Takes ranked topics from topic_ranker and generates concrete
video/post ideas using Gemini Flash.
"""

import json
import os
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def generate_weekly_plan(ranked_topics: list[dict]) -> dict:
    """
    Generate a weekly content plan from ranked topics.
    Returns {youtube: [...], instagram: [...]}.
    """
    # Format top topics as context
    topics_text = "\n".join(
        f"- [{t['niche']}] {t['topic']} (score: {t['score']}, sources: {', '.join(t['sources'])})"
        for t in ranked_topics[:30]
    )

    prompt = f"""You are a YouTube and Instagram content strategist for faceless channels.

Based on these trending topics ranked by engagement potential:

{topics_text}

Generate a weekly content plan:

1. **5 YouTube video ideas** — each should be a 8-12 minute faceless narrated video. Include:
   - title (clickbait but accurate, max 60 chars)
   - niche
   - hook (first 10 seconds to grab attention)
   - angle (what makes this video unique vs existing content)

2. **7 Instagram post ideas** — mix of carousels (5-10 slides) and reels (30-60 sec). Include:
   - type (carousel or reel)
   - title/hook
   - niche
   - content_summary (what the slides/reel covers)

Pick topics with the HIGHEST scores and from DIFFERENT niches for variety.
Avoid generic topics — be specific and timely.

Return ONLY valid JSON:
{{
  "youtube": [
    {{"title": "...", "niche": "...", "hook": "...", "angle": "..."}}
  ],
  "instagram": [
    {{"type": "carousel|reel", "title": "...", "niche": "...", "content_summary": "..."}}
  ]
}}"""

    try:
        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        result = json.loads(response.text)

        yt = result.get("youtube", [])[:5]
        ig = result.get("instagram", [])[:7]
        logger.info(f"Generated plan: {len(yt)} YouTube + {len(ig)} Instagram ideas")
        return {"youtube": yt, "instagram": ig}

    except Exception as e:
        logger.error(f"Suggestion generation failed: {e}")
        return {"youtube": [], "instagram": []}


def format_plan_for_telegram(plan: dict) -> str:
    """Format the weekly plan as a readable Telegram message."""
    lines = ["📋 *Wochenplan — Content-Vorschläge*\n"]

    lines.append("🎬 *YouTube Videos:*")
    for i, v in enumerate(plan.get("youtube", []), 1):
        lines.append(f"\n*{i}. {v.get('title', '?')}*")
        lines.append(f"   Nische: {v.get('niche', '?')}")
        lines.append(f"   Hook: {v.get('hook', '?')}")
        lines.append(f"   Angle: {v.get('angle', '?')}")

    lines.append("\n\n📸 *Instagram Posts:*")
    for i, p in enumerate(plan.get("instagram", []), 1):
        emoji = "🖼" if p.get("type") == "carousel" else "🎬"
        lines.append(f"\n{emoji} *{i}. {p.get('title', '?')}* ({p.get('type', '?')})")
        lines.append(f"   Nische: {p.get('niche', '?')}")
        lines.append(f"   Inhalt: {p.get('content_summary', '?')}")

    lines.append("\n\n💬 Antworte mit den Nummern die ich produzieren soll, z.B.:")
    lines.append("'YouTube 1,3,5 und Instagram 2,4,6'")
    lines.append("Oder 'alle' für den kompletten Plan.")

    return "\n".join(lines)
```

- [ ] **Step 2: Test suggestion generator**

```bash
cd /Users/admin/Documents/BotProjects/agents
python3 -c "
import os
os.environ['GEMINI_API_KEY'] = '$(grep GEMINI_API_KEY /Users/admin/tuby/.env | cut -d= -f2)'
from aca.topic_ranker import get_top_topics_flat
from aca.suggestion_generator import generate_weekly_plan, format_plan_for_telegram
topics = get_top_topics_flat(days=7, top_n=20)
print(f'Got {len(topics)} ranked topics')
plan = generate_weekly_plan(topics)
print(f'YouTube: {len(plan[\"youtube\"])}, Instagram: {len(plan[\"instagram\"])}')
msg = format_plan_for_telegram(plan)
print(msg[:500])
"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/admin/Documents/BotProjects
git add agents/aca/suggestion_generator.py
git commit -m "feat(aca): add suggestion generator with Gemini Flash"
```

---

### Task 4: Susi Bridge

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/susi_bridge.py`

Sends the weekly plan to Thomas via Susi's Telegram bot. Stores the pending plan for approval tracking.

- [ ] **Step 1: Create susi_bridge.py**

```python
"""
aca/susi_bridge.py — Bridge between ACA Brain and Susi.

Sends content plans to Thomas via Susi's Telegram bot.
Stores pending plans for approval tracking.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Susi sends the message, not a separate bot
SUSI_TELEGRAM_TOKEN = os.getenv("SUSI_TELEGRAM_TOKEN", "")
SUSI_CHAT_ID = os.getenv("SUSI_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))

# Pending plans stored here
PLANS_DIR = Path(__file__).resolve().parent.parent.parent / "meta_memory" / "aca_plans"
PLANS_DIR.mkdir(parents=True, exist_ok=True)


def send_to_susi(text: str) -> bool:
    """Send a message to Thomas via Susi's Telegram bot."""
    token = SUSI_TELEGRAM_TOKEN
    chat_id = SUSI_CHAT_ID

    if not token or not chat_id:
        logger.warning("Susi Telegram not configured (SUSI_TELEGRAM_TOKEN / SUSI_CHAT_ID)")
        return False

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            logger.info("Plan sent to Thomas via Susi")
            return True
        else:
            logger.error(f"Telegram send failed: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def save_pending_plan(plan: dict, week: str = "") -> str:
    """Save a plan as pending approval. Returns the plan ID."""
    if not week:
        week = datetime.now(timezone.utc).strftime("%Y-W%V")

    plan_id = f"plan_{week}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    plan_file = PLANS_DIR / f"{plan_id}.json"

    data = {
        "id": plan_id,
        "week": week,
        "status": "pending",
        "plan": plan,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_youtube": [],
        "approved_instagram": [],
    }

    plan_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info(f"Plan saved: {plan_id}")
    return plan_id


def get_pending_plan() -> dict | None:
    """Get the most recent pending plan."""
    plans = sorted(PLANS_DIR.glob("plan_*.json"), reverse=True)
    for pf in plans:
        try:
            data = json.loads(pf.read_text())
            if data.get("status") == "pending":
                return data
        except Exception:
            continue
    return None


def approve_plan(plan_id: str, youtube_indices: list[int], instagram_indices: list[int]) -> dict:
    """Approve specific items from a plan."""
    plan_file = PLANS_DIR / f"{plan_id}.json"
    if not plan_file.exists():
        return {"error": f"Plan {plan_id} not found"}

    data = json.loads(plan_file.read_text())
    data["status"] = "approved"
    data["approved_youtube"] = youtube_indices
    data["approved_instagram"] = instagram_indices
    data["approved_at"] = datetime.now(timezone.utc).isoformat()

    plan_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info(f"Plan {plan_id} approved: YT={youtube_indices}, IG={instagram_indices}")
    return data
```

- [ ] **Step 2: Add Susi Telegram token to BotProjects .env**

```bash
SUSI_TOKEN=$(grep SUSI_TELEGRAM_TOKEN /Users/admin/virtual-assistant/.env | cut -d= -f2)
echo "" >> /Users/admin/Documents/BotProjects/.env
echo "# Susi Telegram (for ACA → Thomas communication)" >> /Users/admin/Documents/BotProjects/.env
echo "SUSI_TELEGRAM_TOKEN=$SUSI_TOKEN" >> /Users/admin/Documents/BotProjects/.env
echo "SUSI_CHAT_ID=1165127208" >> /Users/admin/Documents/BotProjects/.env
```

- [ ] **Step 3: Test susi_bridge**

```bash
cd /Users/admin/Documents/BotProjects/agents
python3 -c "
from aca.susi_bridge import save_pending_plan, get_pending_plan
plan = {'youtube': [{'title': 'Test Video', 'niche': 'stoicism'}], 'instagram': []}
plan_id = save_pending_plan(plan)
print(f'Saved: {plan_id}')
pending = get_pending_plan()
print(f'Pending: {pending[\"id\"]}')
print('Bridge works!')
"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/admin/Documents/BotProjects
git add agents/aca/susi_bridge.py
git commit -m "feat(aca): add Susi bridge for Telegram communication"
```

---

### Task 5: ACA Brain Orchestrator

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/brain.py`

The main orchestrator that ties everything together: ranking → suggestions → send to Susi.

- [ ] **Step 1: Create brain.py**

```python
"""
aca/brain.py — ACA Brain orchestrator.

Weekly cycle:
1. Read signals from last 7 days
2. Rank topics
3. Generate content suggestions (Gemini Flash)
4. Send to Thomas via Susi
5. Wait for approval
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aca.topic_ranker import get_top_topics_flat
from aca.suggestion_generator import generate_weekly_plan, format_plan_for_telegram
from aca.susi_bridge import send_to_susi, save_pending_plan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [aca-brain] %(levelname)s: %(message)s")
logger = logging.getLogger("aca-brain")


def run_weekly_planning() -> dict:
    """
    Full weekly planning cycle:
    1. Rank topics from signals
    2. Generate content plan
    3. Send to Thomas via Susi
    4. Save pending plan for approval
    """
    logger.info("Starting weekly planning cycle...")

    # Step 1: Get ranked topics
    topics = get_top_topics_flat(days=7, top_n=30)
    if not topics:
        msg = "Keine Trend-Signale in den letzten 7 Tagen. Sensing-Collector prüfen."
        send_to_susi(f"⚠️ ACA: {msg}")
        return {"status": "no_signals", "message": msg}

    logger.info(f"Got {len(topics)} ranked topics")

    # Step 2: Generate suggestions
    plan = generate_weekly_plan(topics)
    yt_count = len(plan.get("youtube", []))
    ig_count = len(plan.get("instagram", []))

    if yt_count == 0 and ig_count == 0:
        msg = "Konnte keine Content-Vorschläge generieren. Gemini evtl. nicht erreichbar."
        send_to_susi(f"⚠️ ACA: {msg}")
        return {"status": "generation_failed", "message": msg}

    logger.info(f"Generated plan: {yt_count} YouTube + {ig_count} Instagram")

    # Step 3: Save pending plan
    plan_id = save_pending_plan(plan)

    # Step 4: Send to Thomas via Susi
    telegram_text = format_plan_for_telegram(plan)
    sent = send_to_susi(telegram_text)

    return {
        "status": "sent" if sent else "send_failed",
        "plan_id": plan_id,
        "youtube_count": yt_count,
        "instagram_count": ig_count,
        "topics_analyzed": len(topics),
    }


if __name__ == "__main__":
    result = run_weekly_planning()
    print(f"Result: {result}")
```

- [ ] **Step 2: Test brain end-to-end (dry run, no Telegram)**

```bash
cd /Users/admin/Documents/BotProjects/agents
python3 -c "
import os
os.environ['GEMINI_API_KEY'] = '$(grep GEMINI_API_KEY /Users/admin/tuby/.env | cut -d= -f2)'
# Don't set SUSI_TELEGRAM_TOKEN — will skip sending, just test planning
from aca.brain import run_weekly_planning
result = run_weekly_planning()
print(result)
"
```

Expected: status = "send_failed" (no token), but plan_id should be set and plan saved.

- [ ] **Step 3: Commit**

```bash
cd /Users/admin/Documents/BotProjects
git add agents/aca/brain.py
git commit -m "feat(aca): add brain orchestrator for weekly planning"
```

---

### Task 6: Wire brain to scheduler

**Files:**
- Modify: `~/Documents/BotProjects/agents/scheduler.py`

- [ ] **Step 1: Add brain schedule to scheduler.py**

Add import at top (near the existing aca import):
```python
from aca.brain import run_weekly_planning
```

Add job after the sensing jobs:
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

- [ ] **Step 2: Commit**

```bash
cd /Users/admin/Documents/BotProjects
git add agents/scheduler.py
git commit -m "feat(aca): schedule weekly brain planning on Sunday 20:00"
```

---

### Task 7: Test full pipeline + send test plan to Thomas

- [ ] **Step 1: Run brain with Telegram sending**

```bash
cd /Users/admin/Documents/BotProjects/agents
python3 -c "
import os
os.environ['GEMINI_API_KEY'] = '$(grep GEMINI_API_KEY /Users/admin/tuby/.env | cut -d= -f2)'
os.environ['SUSI_TELEGRAM_TOKEN'] = '$(grep SUSI_TELEGRAM_TOKEN /Users/admin/virtual-assistant/.env | cut -d= -f2)'
os.environ['SUSI_CHAT_ID'] = '1165127208'
from aca.brain import run_weekly_planning
result = run_weekly_planning()
print(result)
"
```

Expected: Thomas receives a formatted weekly content plan on Telegram from Susi.

- [ ] **Step 2: Restart scheduler**

```bash
launchctl kickstart -k gui/$(id -u)/com.tubeclone.scheduler
```

- [ ] **Step 3: Final commit**

```bash
cd /Users/admin/Documents/BotProjects
git add -A
git commit -m "feat(aca): Phase 2 ACA Brain complete — weekly planning + Susi integration"
```
