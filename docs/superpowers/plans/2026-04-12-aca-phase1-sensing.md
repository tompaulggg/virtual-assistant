# ACA Phase 1: Sensing Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a data collection layer that continuously gathers trend signals from YouTube, Google Trends, Reddit, and News APIs into a `signals` table in the Tuby SQLite DB.

**Architecture:** A new `aca/` directory in BotProjects/agents with one collector module per data source. A shared `signals_db.py` handles writes. The existing `scheduler.py` triggers collectors on their respective intervals. No LLM needed — pure API calls and scraping.

**Tech Stack:** Python, pytrends, praw (Reddit), newsapi-python, YouTube Data API v3, SQLite

---

## File Structure

```
~/Documents/BotProjects/agents/aca/
├── __init__.py
├── signals_db.py          # Read/write signals table, schema init
├── collector_trends.py    # Google Trends via pytrends
├── collector_reddit.py    # Reddit hot posts via praw
├── collector_news.py      # News via NewsAPI
├── collector_youtube.py   # YouTube trending via Data API
└── run_sensing.py         # Runs all collectors, called by scheduler
```

**Modify:**
- `~/Documents/BotProjects/agents/scheduler.py` — add sensing schedule
- `~/tuby/services/db.py` — add signals table to init_db()

---

### Task 1: Install dependencies

**Files:**
- Modify: `~/Documents/BotProjects/agents/requirements.txt`

- [ ] **Step 1: Install libraries**

```bash
pip3 install pytrends praw newsapi-python
```

- [ ] **Step 2: Add to requirements.txt**

Append to `~/Documents/BotProjects/agents/requirements.txt`:

```
pytrends>=4.9.0
praw>=7.7.0
newsapi-python>=0.2.7
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/requirements.txt
git commit -m "chore: add sensing layer dependencies"
```

---

### Task 2: Create signals DB layer

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/__init__.py`
- Create: `~/Documents/BotProjects/agents/aca/signals_db.py`

- [ ] **Step 1: Create aca directory and __init__.py**

```bash
mkdir -p ~/Documents/BotProjects/agents/aca
touch ~/Documents/BotProjects/agents/aca/__init__.py
```

- [ ] **Step 2: Create signals_db.py**

```python
"""
aca/signals_db.py — Signals table for trend data collection.

All collectors write normalized signals here. The ACA Brain reads them
to rank topics for content planning.
"""

import json
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / "tuby" / "channels.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_signals_table():
    """Create signals table if not exists."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                niche TEXT NOT NULL,
                topic TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0,
                raw_data TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_source ON signals(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_niche ON signals(niche)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_created ON signals(created_at)")
        conn.commit()
        logger.info("Signals table ready")
    finally:
        conn.close()


def save_signal(source: str, niche: str, topic: str, score: float, raw_data: dict = None):
    """Write a single signal to the DB."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO signals (source, niche, topic, score, raw_data, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                source,
                niche,
                topic,
                score,
                json.dumps(raw_data or {}, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_signals_batch(signals: list[dict]):
    """Write multiple signals at once. Each dict: {source, niche, topic, score, raw_data}."""
    if not signals:
        return
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.executemany(
            "INSERT INTO signals (source, niche, topic, score, raw_data, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    s["source"],
                    s["niche"],
                    s["topic"],
                    s.get("score", 0),
                    json.dumps(s.get("raw_data", {}), ensure_ascii=False),
                    now,
                )
                for s in signals
            ],
        )
        conn.commit()
        logger.info(f"Saved {len(signals)} signals")
    finally:
        conn.close()


def get_signals(days: int = 7, source: str = "", niche: str = "") -> list[dict]:
    """Read signals from the last N days, optionally filtered."""
    conn = _get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conditions = ["created_at >= ?"]
    params = [cutoff]

    if source:
        conditions.append("source = ?")
        params.append(source)
    if niche:
        conditions.append("niche = ?")
        params.append(niche)

    where = " AND ".join(conditions)
    try:
        rows = conn.execute(
            f"SELECT * FROM signals WHERE {where} ORDER BY score DESC", params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_signal_count(days: int = 1) -> int:
    """Count signals in the last N days."""
    conn = _get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE created_at >= ?", (cutoff,)
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()
```

- [ ] **Step 3: Test DB layer**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.signals_db import init_signals_table, save_signal, get_signals, get_signal_count
init_signals_table()
save_signal('test', 'stoicism', 'marcus aurelius quotes', 85.0, {'source_url': 'test'})
signals = get_signals(days=1)
print(f'Signals: {len(signals)}, first: {signals[0][\"topic\"]}')
count = get_signal_count(days=1)
print(f'Count last 24h: {count}')
print('DB layer works!')
"
```

Expected: `Signals: 1, first: marcus aurelius quotes` + `Count last 24h: 1`

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/
git commit -m "feat(aca): add signals DB layer"
```

---

### Task 3: Google Trends collector

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/collector_trends.py`

- [ ] **Step 1: Create collector_trends.py**

```python
"""
aca/collector_trends.py — Google Trends data collector.

Uses pytrends to fetch rising search queries for configured niches.
Runs daily. No API key needed.
"""

import logging
from pytrends.request import TrendReq

from aca.signals_db import save_signals_batch

logger = logging.getLogger(__name__)

# Map niche names to Google Trends search terms
NICHE_KEYWORDS = {
    "stoicism": ["stoicism", "marcus aurelius", "stoic philosophy"],
    "finance": ["investing tips", "passive income", "stock market"],
    "psychology": ["dark psychology", "psychology facts", "manipulation tactics"],
    "history": ["ancient history", "historical mysteries", "forgotten history"],
    "science": ["science facts", "space discovery", "quantum physics"],
    "health": ["health tips", "nutrition facts", "fitness motivation"],
    "true_crime": ["true crime", "unsolved mysteries", "serial killer documentary"],
    "motivation": ["self improvement", "motivation", "productivity tips"],
    "animals": ["animal facts", "wildlife documentary", "cat behavior"],
    "horror": ["scary stories", "creepypasta", "horror narration"],
}


def collect_trends(niches: list[str] = None) -> int:
    """
    Fetch rising queries from Google Trends for each niche.
    Returns number of signals saved.
    """
    if niches is None:
        niches = list(NICHE_KEYWORDS.keys())

    pytrends = TrendReq(hl="en-US", tz=360)
    all_signals = []

    for niche in niches:
        keywords = NICHE_KEYWORDS.get(niche, [niche])
        for kw in keywords:
            try:
                pytrends.build_payload([kw], cat=0, timeframe="now 7-d")
                related = pytrends.related_queries()

                rising = related.get(kw, {}).get("rising")
                if rising is not None and not rising.empty:
                    for _, row in rising.head(10).iterrows():
                        all_signals.append({
                            "source": "google_trends",
                            "niche": niche,
                            "topic": row["query"],
                            "score": min(float(row["value"]), 100),
                            "raw_data": {"keyword": kw, "type": "rising"},
                        })

                top = related.get(kw, {}).get("top")
                if top is not None and not top.empty:
                    for _, row in top.head(5).iterrows():
                        all_signals.append({
                            "source": "google_trends",
                            "niche": niche,
                            "topic": row["query"],
                            "score": float(row["value"]),
                            "raw_data": {"keyword": kw, "type": "top"},
                        })

            except Exception as e:
                logger.warning(f"Google Trends failed for '{kw}': {e}")

    save_signals_batch(all_signals)
    logger.info(f"Google Trends: {len(all_signals)} signals from {len(niches)} niches")
    return len(all_signals)
```

- [ ] **Step 2: Test Google Trends collector**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.signals_db import init_signals_table
from aca.collector_trends import collect_trends
init_signals_table()
count = collect_trends(['stoicism'])
print(f'Collected {count} trend signals')
"
```

Expected: `Collected N trend signals` (N > 0)

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/collector_trends.py
git commit -m "feat(aca): add Google Trends collector"
```

---

### Task 4: Reddit collector

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/collector_reddit.py`

Reddit API is free with a script-type app. Thomas needs to create one at https://www.reddit.com/prefs/apps (one-time setup, takes 30 seconds).

- [ ] **Step 1: Create collector_reddit.py**

```python
"""
aca/collector_reddit.py — Reddit hot posts collector.

Scrapes hot posts from niche-relevant subreddits.
Runs every 4h. Requires Reddit API credentials (free).
"""

import os
import logging
import praw

from aca.signals_db import save_signals_batch

logger = logging.getLogger(__name__)

# Map niches to relevant subreddits
NICHE_SUBREDDITS = {
    "stoicism": ["Stoicism", "philosophy", "StoicMemes"],
    "finance": ["personalfinance", "investing", "Fire"],
    "psychology": ["psychology", "socialskills", "selfimprovement"],
    "history": ["history", "AskHistorians", "HistoryMemes"],
    "science": ["science", "space", "Futurology"],
    "health": ["fitness", "nutrition", "loseit"],
    "true_crime": ["TrueCrime", "UnresolvedMysteries", "serialkillers"],
    "motivation": ["getdisciplined", "DecidingToBeBetter", "productivity"],
    "animals": ["NatureIsFuckingLit", "Awwducational", "AnimalFacts"],
    "horror": ["nosleep", "creepypasta", "LetsNotMeet"],
    "youtube_meta": ["YoutubeAutomation", "NewTubers", "PartneredYoutube"],
}


def collect_reddit(niches: list[str] = None) -> int:
    """
    Fetch hot posts from niche subreddits.
    Returns number of signals saved.
    """
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        logger.warning("Reddit credentials not configured (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)")
        return 0

    if niches is None:
        niches = list(NICHE_SUBREDDITS.keys())

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="aca-sensing/1.0",
    )

    all_signals = []

    for niche in niches:
        subreddits = NICHE_SUBREDDITS.get(niche, [])
        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=10):
                    if post.stickied:
                        continue
                    # Score = upvotes normalized (log scale, max 100)
                    import math
                    score = min(100, round(math.log10(max(post.score, 1)) * 25))

                    all_signals.append({
                        "source": "reddit",
                        "niche": niche,
                        "topic": post.title,
                        "score": score,
                        "raw_data": {
                            "subreddit": sub_name,
                            "upvotes": post.score,
                            "comments": post.num_comments,
                            "url": f"https://reddit.com{post.permalink}",
                        },
                    })
            except Exception as e:
                logger.warning(f"Reddit failed for r/{sub_name}: {e}")

    save_signals_batch(all_signals)
    logger.info(f"Reddit: {len(all_signals)} signals from {len(niches)} niches")
    return len(all_signals)
```

- [ ] **Step 2: Add Reddit env vars to .env**

Append to `~/Documents/BotProjects/.env`:

```
# Reddit API (free, create at https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
```

Thomas fills these in after creating a Reddit app (type: script, redirect: http://localhost:8080).

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/collector_reddit.py
git commit -m "feat(aca): add Reddit collector"
```

---

### Task 5: News collector

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/collector_news.py`

Uses NewsAPI (free tier: 100 requests/day).

- [ ] **Step 1: Create collector_news.py**

```python
"""
aca/collector_news.py — News headline collector.

Fetches breaking news headlines relevant to configured niches.
Runs every 4h. Free tier: 100 requests/day.
"""

import os
import logging
from newsapi import NewsApiClient

from aca.signals_db import save_signals_batch

logger = logging.getLogger(__name__)

# Map niches to NewsAPI search queries
NICHE_QUERIES = {
    "stoicism": "stoicism OR marcus aurelius OR philosophy",
    "finance": "investing OR stock market OR cryptocurrency",
    "psychology": "psychology OR mental health OR neuroscience",
    "history": "archaeological discovery OR ancient history",
    "science": "space discovery OR science breakthrough OR quantum",
    "health": "nutrition study OR fitness research OR health discovery",
    "true_crime": "crime investigation OR cold case OR serial killer",
    "motivation": "self improvement OR productivity OR success story",
    "animals": "wildlife discovery OR animal behavior OR nature documentary",
    "horror": "paranormal OR unexplained OR mysterious disappearance",
}


def collect_news(niches: list[str] = None) -> int:
    """
    Fetch recent news headlines for each niche.
    Returns number of signals saved.
    """
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        logger.warning("NewsAPI key not configured (NEWSAPI_KEY)")
        return 0

    if niches is None:
        niches = list(NICHE_QUERIES.keys())

    newsapi = NewsApiClient(api_key=api_key)
    all_signals = []

    for niche in niches:
        query = NICHE_QUERIES.get(niche, niche)
        try:
            response = newsapi.get_everything(
                q=query,
                language="en",
                sort_by="relevancy",
                page_size=10,
            )
            for article in response.get("articles", []):
                title = article.get("title", "")
                if not title or title == "[Removed]":
                    continue

                all_signals.append({
                    "source": "news",
                    "niche": niche,
                    "topic": title,
                    "score": 50,  # News has no score; flat weight, recency matters
                    "raw_data": {
                        "source_name": article.get("source", {}).get("name", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "description": (article.get("description") or "")[:200],
                    },
                })
        except Exception as e:
            logger.warning(f"NewsAPI failed for niche '{niche}': {e}")

    save_signals_batch(all_signals)
    logger.info(f"News: {len(all_signals)} signals from {len(niches)} niches")
    return len(all_signals)
```

- [ ] **Step 2: Add NewsAPI env var**

Append to `~/Documents/BotProjects/.env`:

```
# NewsAPI (free: 100 req/day, get key at https://newsapi.org)
NEWSAPI_KEY=
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/collector_news.py
git commit -m "feat(aca): add News collector"
```

---

### Task 6: YouTube Trending collector

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/collector_youtube.py`

Uses existing YouTube Data API key from Tuby.

- [ ] **Step 1: Create collector_youtube.py**

```python
"""
aca/collector_youtube.py — YouTube trending videos collector.

Fetches recently popular videos in niche categories via YouTube Data API.
Runs every 6h. Uses Tuby's existing YouTube API key.
"""

import os
import logging
from googleapiclient.discovery import build

from aca.signals_db import save_signals_batch

logger = logging.getLogger(__name__)

# Niche → YouTube search queries for trending content
NICHE_SEARCHES = {
    "stoicism": ["stoicism", "marcus aurelius motivation"],
    "finance": ["passive income 2026", "investing for beginners"],
    "psychology": ["dark psychology", "psychology facts"],
    "history": ["history documentary", "ancient mysteries"],
    "science": ["science explained", "space documentary 2026"],
    "health": ["health tips", "nutrition facts"],
    "true_crime": ["true crime documentary", "unsolved mystery"],
    "motivation": ["self improvement", "productivity tips"],
    "animals": ["animal facts", "wildlife documentary"],
    "horror": ["scary stories narrated", "creepypasta"],
}


def _get_youtube():
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not set")
    return build("youtube", "v3", developerKey=key)


def collect_youtube_trending(niches: list[str] = None) -> int:
    """
    Search for recent high-performing videos in each niche.
    Returns number of signals saved.
    """
    if niches is None:
        niches = list(NICHE_SEARCHES.keys())

    try:
        yt = _get_youtube()
    except RuntimeError as e:
        logger.warning(str(e))
        return 0

    all_signals = []

    for niche in niches:
        queries = NICHE_SEARCHES.get(niche, [niche])
        for query in queries:
            try:
                response = yt.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    order="viewCount",
                    publishedAfter=_days_ago_rfc3339(7),
                    maxResults=10,
                    relevanceLanguage="en",
                ).execute()

                video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
                if not video_ids:
                    continue

                stats_response = yt.videos().list(
                    part="statistics,snippet",
                    id=",".join(video_ids),
                ).execute()

                for video in stats_response.get("items", []):
                    views = int(video["statistics"].get("viewCount", 0))
                    title = video["snippet"]["title"]

                    import math
                    score = min(100, round(math.log10(max(views, 1)) * 15))

                    all_signals.append({
                        "source": "youtube_trending",
                        "niche": niche,
                        "topic": title,
                        "score": score,
                        "raw_data": {
                            "video_id": video["id"],
                            "views": views,
                            "likes": int(video["statistics"].get("likeCount", 0)),
                            "channel": video["snippet"].get("channelTitle", ""),
                            "published_at": video["snippet"].get("publishedAt", ""),
                        },
                    })

            except Exception as e:
                logger.warning(f"YouTube trending failed for '{query}': {e}")

    save_signals_batch(all_signals)
    logger.info(f"YouTube Trending: {len(all_signals)} signals from {len(niches)} niches")
    return len(all_signals)


def _days_ago_rfc3339(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 2: Add YouTube API key to BotProjects .env**

Append to `~/Documents/BotProjects/.env`:

```
# YouTube Data API (shared with Tuby)
YOUTUBE_API_KEY=<copy from ~/tuby/.env>
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/collector_youtube.py
git commit -m "feat(aca): add YouTube Trending collector"
```

---

### Task 7: Sensing runner + scheduler integration

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/run_sensing.py`
- Modify: `~/Documents/BotProjects/agents/scheduler.py`

- [ ] **Step 1: Create run_sensing.py**

```python
"""
aca/run_sensing.py — Run all sensing collectors.

Called by scheduler or manually. Initializes DB, runs all collectors,
prints summary.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aca.signals_db import init_signals_table, get_signal_count
from aca.collector_trends import collect_trends
from aca.collector_reddit import collect_reddit
from aca.collector_news import collect_news
from aca.collector_youtube import collect_youtube_trending

logging.basicConfig(level=logging.INFO, format="%(asctime)s [sensing] %(levelname)s: %(message)s")
logger = logging.getLogger("sensing")


def run_all_collectors() -> dict:
    """Run all collectors and return summary."""
    init_signals_table()

    results = {}
    collectors = [
        ("google_trends", collect_trends),
        ("reddit", collect_reddit),
        ("news", collect_news),
        ("youtube_trending", collect_youtube_trending),
    ]

    for name, func in collectors:
        try:
            count = func()
            results[name] = count
            logger.info(f"{name}: {count} signals")
        except Exception as e:
            results[name] = f"error: {e}"
            logger.error(f"{name} failed: {e}")

    total = sum(v for v in results.values() if isinstance(v, int))
    logger.info(f"Sensing complete: {total} total signals")
    return results


def run_collector(name: str) -> int:
    """Run a single collector by name."""
    init_signals_table()
    collectors = {
        "google_trends": collect_trends,
        "reddit": collect_reddit,
        "news": collect_news,
        "youtube_trending": collect_youtube_trending,
    }
    func = collectors.get(name)
    if not func:
        raise ValueError(f"Unknown collector: {name}. Available: {list(collectors.keys())}")
    return func()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        name = sys.argv[1]
        count = run_collector(name)
        print(f"{name}: {count} signals")
    else:
        results = run_all_collectors()
        for k, v in results.items():
            print(f"  {k}: {v}")
```

- [ ] **Step 2: Add sensing to scheduler.py**

In `~/Documents/BotProjects/agents/scheduler.py`, add the import at the top (after existing imports):

```python
from aca.run_sensing import run_collector
```

Add these scheduled jobs (after the existing `schedule.every().day.at(...)` block, before `while True`):

```python
# ── ACA Sensing Layer ──────────────────────────────────────────────────────
def _run_sensing(collector_name):
    def _inner():
        try:
            logger.info(f"Sensing: {collector_name}")
            count = run_collector(collector_name)
            logger.info(f"Sensing done: {collector_name} — {count} signals")
        except Exception as e:
            logger.error(f"Sensing failed: {collector_name} — {e}")
    return _inner

schedule.every().day.at("05:00").do(_run_sensing("google_trends"))
schedule.every(4).hours.do(_run_sensing("reddit"))
schedule.every(4).hours.do(_run_sensing("news"))
schedule.every(6).hours.do(_run_sensing("youtube_trending"))
logger.info("ACA sensing jobs scheduled")
```

- [ ] **Step 3: Test run_sensing manually**

```bash
cd ~/Documents/BotProjects/agents
python3 -m aca.run_sensing google_trends
```

Expected: `google_trends: N signals` (N > 0, may take 30-60 seconds)

- [ ] **Step 4: Test full sensing run**

```bash
cd ~/Documents/BotProjects/agents
python3 -m aca.run_sensing
```

Expected: Summary with counts per collector. Reddit/News may show 0 if API keys aren't configured yet — that's OK.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/run_sensing.py agents/scheduler.py
git commit -m "feat(aca): wire sensing collectors to scheduler"
```

---

### Task 8: Verify end-to-end + restart scheduler

- [ ] **Step 1: Check signals in DB**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.signals_db import init_signals_table, get_signals, get_signal_count
init_signals_table()
count = get_signal_count(days=1)
signals = get_signals(days=1)
print(f'Total signals last 24h: {count}')
sources = {}
for s in signals:
    sources[s['source']] = sources.get(s['source'], 0) + 1
for src, n in sorted(sources.items()):
    print(f'  {src}: {n}')
if signals:
    print(f'Top signal: {signals[0][\"topic\"]} (score={signals[0][\"score\"]}, source={signals[0][\"source\"]})')
"
```

Expected: At least Google Trends signals present.

- [ ] **Step 2: Restart scheduler**

```bash
launchctl kickstart -k gui/$(id -u)/com.tubeclone.scheduler
```

- [ ] **Step 3: Commit all remaining changes**

```bash
cd ~/Documents/BotProjects
git add -A
git commit -m "feat(aca): Phase 1 Sensing Layer complete"
```
