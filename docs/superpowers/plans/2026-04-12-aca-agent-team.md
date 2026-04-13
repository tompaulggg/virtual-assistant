# ACA Agent Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three specialized agents (Performance Analyst, SEO Agent, Thumbnail Artist) that the ACA Brain can call to improve content quality and learn from results.

**Architecture:** Each agent is a standalone Python module in `aca/agents/` with a clear function interface. They share the Tuby SQLite DB for data. The Performance Analyst tracks metrics daily, the SEO Agent optimizes metadata per video, and the Thumbnail Artist generates visual options. All communicate results via the existing Susi bridge.

**Tech Stack:** Python, yt-dlp (scraping), Pillow (text overlay), FLUX via Replicate (image gen), Gemini Flash (analysis), Haiku (text gen), SQLite

---

## File Structure

```
~/Documents/BotProjects/agents/aca/agents/
├── __init__.py
├── performance_analyst.py   # Daily metric tracking + weekly summary
├── seo_agent.py             # Title/Tags/Description optimization
└── thumbnail_artist.py      # Thumbnail generation with text overlay
```

**Modify:**
- `~/Documents/BotProjects/agents/aca/signals_db.py` — add performance_log table
- `~/Documents/BotProjects/agents/scheduler.py` — add daily tracking + weekly summary jobs

---

### Task 1: Performance log DB schema

**Files:**
- Modify: `~/Documents/BotProjects/agents/aca/signals_db.py`
- Create: `~/Documents/BotProjects/agents/aca/agents/__init__.py`

- [ ] **Step 1: Create agents directory**

```bash
mkdir -p ~/Documents/BotProjects/agents/aca/agents
touch ~/Documents/BotProjects/agents/aca/agents/__init__.py
```

- [ ] **Step 2: Add performance_log table to signals_db.py**

Add this function to the end of `/Users/admin/Documents/BotProjects/agents/aca/signals_db.py`:

```python
def init_performance_table():
    """Create performance_log table if not exists."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS performance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'youtube',
                date TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                impressions INTEGER,
                ctr REAL,
                avg_retention REAL,
                watch_time_hours REAL,
                subscriber_gain INTEGER,
                traffic_source_browse REAL,
                traffic_source_search REAL,
                traffic_source_suggested REAL,
                traffic_source_external REAL,
                revenue_usd REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_perf_video ON performance_log(video_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_log(date)")
        conn.commit()
        logger.info("Performance log table ready")
    finally:
        conn.close()


def save_performance_snapshot(video_id: str, metrics: dict, platform: str = "youtube"):
    """Save a daily performance snapshot for a video."""
    conn = _get_conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        # Check if already tracked today
        existing = conn.execute(
            "SELECT id FROM performance_log WHERE video_id = ? AND date = ? AND platform = ?",
            (video_id, today, platform),
        ).fetchone()
        if existing:
            # Update existing
            conn.execute(
                "UPDATE performance_log SET views=?, likes=?, comments=?, shares=? WHERE id=?",
                (metrics.get("views", 0), metrics.get("likes", 0),
                 metrics.get("comments", 0), metrics.get("shares", 0), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO performance_log (video_id, platform, date, views, likes, comments, shares) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (video_id, platform, today,
                 metrics.get("views", 0), metrics.get("likes", 0),
                 metrics.get("comments", 0), metrics.get("shares", 0)),
            )
        conn.commit()
    finally:
        conn.close()


def get_video_performance(video_id: str, days: int = 30) -> list[dict]:
    """Get performance history for a video."""
    conn = _get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        rows = conn.execute(
            "SELECT * FROM performance_log WHERE video_id = ? AND date >= ? ORDER BY date",
            (video_id, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_tracked_videos() -> list[dict]:
    """Get latest snapshot for each tracked video."""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT p.* FROM performance_log p
            INNER JOIN (
                SELECT video_id, MAX(date) as max_date FROM performance_log GROUP BY video_id
            ) latest ON p.video_id = latest.video_id AND p.date = latest.max_date
            ORDER BY p.views DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 3: Test**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.signals_db import init_performance_table, save_performance_snapshot, get_video_performance
init_performance_table()
save_performance_snapshot('test_vid_1', {'views': 1000, 'likes': 50, 'comments': 10})
history = get_video_performance('test_vid_1')
print(f'Snapshots: {len(history)}, views: {history[0][\"views\"]}')
print('Performance DB works!')
"
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/signals_db.py agents/aca/agents/
git commit -m "feat(aca): add performance_log DB schema"
```

---

### Task 2: Performance Analyst — daily tracking

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/agents/performance_analyst.py`

- [ ] **Step 1: Create performance_analyst.py**

```python
"""
aca/agents/performance_analyst.py — Track video performance daily.

Modus 1 (no OAuth): scrapes via yt-dlp — views, likes, comments.
Modus 2 (OAuth): YouTube Analytics API — CTR, retention, impressions.
Alerts Susi on viral videos or underperformance.
"""

import json
import logging
import subprocess
from datetime import datetime, timezone

from aca.signals_db import (
    init_performance_table,
    save_performance_snapshot,
    get_video_performance,
    get_all_tracked_videos,
)
from aca.susi_bridge import send_to_susi

logger = logging.getLogger(__name__)


def scrape_video_stats(video_id: str) -> dict:
    """Scrape video stats via yt-dlp (no API key needed)."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", f"https://youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f"yt-dlp failed for {video_id}: {result.stderr[:200]}")
            return {}
        data = json.loads(result.stdout)
        return {
            "views": data.get("view_count", 0),
            "likes": data.get("like_count", 0),
            "comments": data.get("comment_count", 0),
            "title": data.get("title", ""),
            "duration": data.get("duration", 0),
        }
    except Exception as e:
        logger.warning(f"Scrape failed for {video_id}: {e}")
        return {}


def track_videos(video_ids: list[str]) -> dict:
    """
    Track a list of video IDs. Saves snapshots and detects anomalies.
    Returns summary dict.
    """
    init_performance_table()
    results = {"tracked": 0, "alerts": []}

    for vid in video_ids:
        stats = scrape_video_stats(vid)
        if not stats:
            continue

        save_performance_snapshot(vid, stats)
        results["tracked"] += 1

        # Check for viral spike
        history = get_video_performance(vid, days=7)
        if len(history) >= 2:
            prev_views = history[-2]["views"]
            curr_views = stats["views"]
            if prev_views > 0 and curr_views > prev_views * 5:
                alert = f"🚀 Video geht viral: '{stats.get('title', vid)}' — {curr_views:,} Views (+{curr_views - prev_views:,} seit gestern)"
                results["alerts"].append(alert)
                send_to_susi(alert)

    logger.info(f"Tracked {results['tracked']} videos, {len(results['alerts'])} alerts")
    return results


def get_underperformers(threshold_pct: float = 0.5) -> list[dict]:
    """
    Find videos performing below threshold_pct of the channel average.
    Returns list of {video_id, views, avg_views, ratio}.
    """
    all_videos = get_all_tracked_videos()
    if not all_videos:
        return []

    avg_views = sum(v["views"] for v in all_videos) / len(all_videos)
    if avg_views == 0:
        return []

    underperformers = []
    for v in all_videos:
        ratio = v["views"] / avg_views
        if ratio < threshold_pct:
            underperformers.append({
                "video_id": v["video_id"],
                "views": v["views"],
                "avg_views": int(avg_views),
                "ratio": round(ratio, 2),
            })

    return underperformers


def generate_weekly_summary(video_ids: list[str]) -> str:
    """
    Generate a text summary of this week's performance.
    No LLM — pure data formatting.
    """
    if not video_ids:
        return "Keine Videos zum Tracken."

    lines = ["📊 *Wochen-Performance*\n"]
    all_videos = get_all_tracked_videos()

    if not all_videos:
        return "Noch keine Performance-Daten vorhanden."

    # Sort by views
    all_videos.sort(key=lambda x: x["views"], reverse=True)

    total_views = sum(v["views"] for v in all_videos)
    avg_views = total_views // len(all_videos) if all_videos else 0

    lines.append(f"Videos: {len(all_videos)} | Total Views: {total_views:,} | Avg: {avg_views:,}\n")

    # Top 3
    lines.append("*Top Videos:*")
    for v in all_videos[:3]:
        lines.append(f"  🏆 {v['video_id']}: {v['views']:,} Views, {v['likes']} Likes")

    # Bottom 3 (underperformers)
    underperformers = [v for v in all_videos if v["views"] < avg_views * 0.5]
    if underperformers:
        lines.append("\n*Underperformer (< 50% avg):*")
        for v in underperformers[:3]:
            lines.append(f"  ⚠️ {v['video_id']}: {v['views']:,} Views")
        lines.append("→ SEO Agent kann Titel/Tags nachoptimieren")

    return "\n".join(lines)
```

- [ ] **Step 2: Test with a real video**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.agents.performance_analyst import scrape_video_stats, track_videos
# Test with a known video
stats = scrape_video_stats('dQw4w9WgXcQ')
print(f'Views: {stats.get(\"views\", 0):,}, Likes: {stats.get(\"likes\", 0):,}')
result = track_videos(['dQw4w9WgXcQ'])
print(f'Tracked: {result[\"tracked\"]}')
"
```

- [ ] **Step 3: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/agents/performance_analyst.py
git commit -m "feat(aca): add Performance Analyst agent"
```

---

### Task 3: SEO Agent

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/agents/seo_agent.py`

- [ ] **Step 1: Create seo_agent.py**

```python
"""
aca/agents/seo_agent.py — Optimize video metadata for YouTube SEO.

Scrapes YouTube Search Suggest + competitor titles from DB.
Generates optimized titles, descriptions, and tags via Haiku.
Can re-optimize underperforming videos after 7 days.
"""

import json
import logging
import os
import sqlite3
import urllib.request
import urllib.parse
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

TUBY_DB = Path.home() / "tuby" / "channels.db"


def scrape_search_suggest(query: str) -> list[str]:
    """Get YouTube autocomplete suggestions for a query. Free, no API key."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            # Response is JSONP: window.google.ac.h([...])
            start = raw.index("[")
            data = json.loads(raw[start:])
            suggestions = [item[0] for item in data[1]] if len(data) > 1 else []
            return suggestions[:10]
    except Exception as e:
        logger.warning(f"Search suggest failed for '{query}': {e}")
        return []


def get_competitor_titles(niche: str, limit: int = 10) -> list[str]:
    """Get top video titles from competitor channels in the niche."""
    if not TUBY_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(TUBY_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT top_videos_json FROM channels WHERE niches LIKE ? AND length(top_videos_json) > 5 "
            "ORDER BY outlier_score DESC LIMIT 20",
            (f"%{niche}%",),
        ).fetchall()
        conn.close()

        titles = []
        for row in rows:
            try:
                videos = json.loads(row["top_videos_json"])
                for v in videos[:3]:
                    if v.get("title"):
                        titles.append(v["title"])
            except (json.JSONDecodeError, KeyError):
                continue
        return titles[:limit]
    except Exception as e:
        logger.warning(f"Competitor titles failed: {e}")
        return []


def optimize_metadata(topic: str, script_summary: str, niche: str) -> dict:
    """
    Generate optimized title, description, and tags for a video.
    Returns {titles: [...], description: str, tags: [...]}.
    """
    # Gather data
    suggestions = scrape_search_suggest(topic)
    competitor_titles = get_competitor_titles(niche)

    prompt = f"""You are a YouTube SEO expert. Generate metadata for a faceless narrated video.

Topic: {topic}
Niche: {niche}
Script summary: {script_summary[:500]}

YouTube Search Suggest for this topic:
{chr(10).join(f'- {s}' for s in suggestions) if suggestions else '(no data)'}

Top competitor video titles in this niche:
{chr(10).join(f'- {t}' for t in competitor_titles[:10]) if competitor_titles else '(no data)'}

Generate:
1. 3 title options (max 60 chars each, clickbait but accurate, use power words)
2. SEO description (500 chars, keywords in first 100 chars, include CTA)
3. 15-20 tags (mix of high-volume short keywords and long-tail phrases)

Return JSON:
{{
  "titles": ["Title 1", "Title 2", "Title 3"],
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Extract JSON from response
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]
        result = json.loads(text)
        logger.info(f"SEO: {len(result.get('titles', []))} titles, {len(result.get('tags', []))} tags")
        return result
    except Exception as e:
        logger.error(f"SEO optimization failed: {e}")
        return {"titles": [], "description": "", "tags": []}


def suggest_reoptimization(video_id: str, current_title: str, niche: str, views: int, avg_views: int) -> dict:
    """
    Suggest new metadata for an underperforming video.
    Returns {new_titles: [...], new_tags: [...], reason: str}.
    """
    suggestions = scrape_search_suggest(current_title.split(" ")[0])  # Search with first word

    prompt = f"""A YouTube video is underperforming. Suggest improved metadata.

Current title: {current_title}
Niche: {niche}
Views after 7 days: {views:,} (channel average: {avg_views:,})

Current search trends for this topic:
{chr(10).join(f'- {s}' for s in suggestions) if suggestions else '(no trend data)'}

The video likely has a title/thumbnail problem. Generate:
1. 3 alternative titles (more clickbait, different angle, max 60 chars)
2. 5 additional tags based on current trends
3. Brief reason why the current title might not work

Return JSON:
{{
  "new_titles": ["...", "...", "..."],
  "new_tags": ["...", "...", "...", "...", "..."],
  "reason": "..."
}}"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]
        return json.loads(text)
    except Exception as e:
        logger.error(f"Reoptimization failed: {e}")
        return {"new_titles": [], "new_tags": [], "reason": "Error"}
```

- [ ] **Step 2: Test SEO agent**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.agents.seo_agent import scrape_search_suggest, get_competitor_titles, optimize_metadata
# Test search suggest
sugg = scrape_search_suggest('stoicism')
print(f'Suggestions: {sugg[:5]}')
# Test competitor titles
titles = get_competitor_titles('stoicism')
print(f'Competitor titles: {len(titles)}')
print(titles[:3])
"
```

- [ ] **Step 3: Test full optimization (needs Anthropic key)**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
import os; os.environ.setdefault('ANTHROPIC_API_KEY', open('/Users/admin/Documents/BotProjects/.env').read().split('ANTHROPIC_API_KEY=')[1].split('\n')[0])
from aca.agents.seo_agent import optimize_metadata
result = optimize_metadata('marcus aurelius daily habits', 'A video about the daily routine of Marcus Aurelius', 'stoicism')
print(f'Titles: {result.get(\"titles\", [])}')
print(f'Tags: {len(result.get(\"tags\", []))} tags')
print(f'Description: {result.get(\"description\", \"\")[:100]}...')
"
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/agents/seo_agent.py
git commit -m "feat(aca): add SEO Agent"
```

---

### Task 4: Thumbnail Artist

**Files:**
- Create: `~/Documents/BotProjects/agents/aca/agents/thumbnail_artist.py`

- [ ] **Step 1: Create thumbnail_artist.py**

```python
"""
aca/agents/thumbnail_artist.py — Generate YouTube thumbnails with text overlay.

1. Gemini Flash analyzes competitor thumbnails and generates FLUX prompts
2. FLUX generates the background image
3. Pillow adds text overlay (max 5 words, bold, high contrast)

Outputs 3 variants per video.
"""

import io
import json
import logging
import os
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path.home() / "Documents" / "BotProjects" / "uploads" / "thumbnails"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = "/System/Library/Fonts/Supplemental/Impact.ttf"
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720


def _get_gemini():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_thumbnail_concepts(title: str, niche: str, competitor_thumbs: list[str] = None) -> list[dict]:
    """
    Use Gemini Flash to generate 3 thumbnail concepts.
    Returns [{prompt, text_overlay, text_color, text_position}].
    """
    thumb_context = ""
    if competitor_thumbs:
        thumb_context = f"\nCompetitor thumbnail URLs for reference (analyze their style): {', '.join(competitor_thumbs[:5])}"

    prompt = f"""You are a YouTube thumbnail designer for faceless channels.

Video title: {title}
Niche: {niche}{thumb_context}

Generate 3 DIFFERENT thumbnail concepts. Each must be visually striking and make someone want to click.

For each concept provide:
- prompt: A detailed image generation prompt for FLUX (cinematic, dramatic lighting, 16:9, no text in image)
- text_overlay: The text to put ON the thumbnail (max 5 words, ALL CAPS, emotional/shocking)
- text_color: hex color for the text (high contrast with the likely background)
- text_position: "top" or "bottom" (where to place the text)

Return JSON array:
[
  {{"prompt": "...", "text_overlay": "...", "text_color": "#FFFFFF", "text_position": "top"}},
  {{"prompt": "...", "text_overlay": "...", "text_color": "#FFD700", "text_position": "bottom"}},
  {{"prompt": "...", "text_overlay": "...", "text_color": "#FF0000", "text_position": "top"}}
]"""

    try:
        response = _get_gemini().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        concepts = json.loads(response.text)
        if isinstance(concepts, list) and len(concepts) >= 1:
            logger.info(f"Generated {len(concepts)} thumbnail concepts")
            return concepts[:3]
    except Exception as e:
        logger.error(f"Concept generation failed: {e}")

    # Fallback: generate basic concepts
    return [
        {"prompt": f"Cinematic dramatic scene related to {niche}, dark moody lighting, 16:9",
         "text_overlay": title.split(":")[0][:30].upper() if ":" in title else title[:30].upper(),
         "text_color": "#FFFFFF", "text_position": "top"},
    ]


def generate_flux_image(prompt: str) -> bytes | None:
    """Generate image via FLUX on Replicate. Returns image bytes."""
    api_token = os.getenv("REPLICATE_API_TOKEN", "")
    if not api_token:
        logger.warning("REPLICATE_API_TOKEN not set")
        return None

    try:
        import replicate
        output = replicate.run(
            "black-forest-labs/flux-1.1-pro",
            input={
                "prompt": prompt,
                "width": THUMB_WIDTH,
                "height": THUMB_HEIGHT,
                "num_inference_steps": 25,
            },
        )
        # output is a FileOutput or URL
        if hasattr(output, 'read'):
            return output.read()
        elif isinstance(output, str):
            resp = httpx.get(output, timeout=30)
            return resp.content
        elif isinstance(output, list) and output:
            resp = httpx.get(str(output[0]), timeout=30)
            return resp.content
    except Exception as e:
        logger.error(f"FLUX generation failed: {e}")
    return None


def add_text_overlay(image_bytes: bytes, text: str, color: str = "#FFFFFF", position: str = "top") -> bytes:
    """Add bold text overlay to thumbnail image using Pillow."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Calculate font size (1/5 of image height)
    font_size = THUMB_HEIGHT // 5
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except OSError:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size)

    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center horizontally, position vertically
    x = (THUMB_WIDTH - text_width) // 2
    if position == "top":
        y = THUMB_HEIGHT // 8
    else:
        y = THUMB_HEIGHT - text_height - THUMB_HEIGHT // 8

    # Draw outline (black, 4px offset in all directions)
    outline_color = "#000000"
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            if abs(dx) + abs(dy) <= 6:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

    # Draw main text
    draw.text((x, y), text, font=font, fill=color)

    # Convert back to bytes
    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=95)
    return output.getvalue()


def create_thumbnails(title: str, niche: str, video_id: str = "", competitor_thumbs: list[str] = None) -> list[str]:
    """
    Full pipeline: concepts → FLUX → text overlay → save.
    Returns list of saved thumbnail file paths.
    """
    concepts = generate_thumbnail_concepts(title, niche, competitor_thumbs)
    saved = []

    vid_dir = OUTPUT_DIR / (video_id or "unnamed")
    vid_dir.mkdir(parents=True, exist_ok=True)

    for i, concept in enumerate(concepts):
        logger.info(f"Generating thumbnail {i + 1}/{len(concepts)}: {concept.get('text_overlay', '')}")

        # Generate background
        image_bytes = generate_flux_image(concept["prompt"])
        if not image_bytes:
            logger.warning(f"Skipping thumbnail {i + 1} — FLUX failed")
            continue

        # Add text overlay
        final = add_text_overlay(
            image_bytes,
            concept.get("text_overlay", title[:30].upper()),
            concept.get("text_color", "#FFFFFF"),
            concept.get("text_position", "top"),
        )

        # Save
        path = vid_dir / f"thumb_{i + 1}.jpg"
        path.write_bytes(final)
        saved.append(str(path))
        logger.info(f"Saved: {path}")

    return saved
```

- [ ] **Step 2: Test text overlay only (no FLUX/Replicate needed)**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
from aca.agents.thumbnail_artist import add_text_overlay
from PIL import Image
import io

# Create a test dark background
img = Image.new('RGB', (1280, 720), color=(30, 30, 50))
img_bytes = io.BytesIO()
img.save(img_bytes, format='JPEG')

result = add_text_overlay(img_bytes.getvalue(), 'HE LIED TO ALL', '#FFD700', 'top')
with open('/tmp/test_thumb.jpg', 'wb') as f:
    f.write(result)
print(f'Thumbnail saved: /tmp/test_thumb.jpg ({len(result)} bytes)')
"
open /tmp/test_thumb.jpg
```

Expected: A dark thumbnail with "HE LIED TO ALL" in gold Impact font with black outline.

- [ ] **Step 3: Test concept generation (needs Gemini)**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
import os; os.environ.setdefault('GEMINI_API_KEY', '$(grep GEMINI_API_KEY /Users/admin/tuby/.env | cut -d= -f2)')
from aca.agents.thumbnail_artist import generate_thumbnail_concepts
concepts = generate_thumbnail_concepts('Marcus Aurelius: 5 Rules That Changed My Life', 'stoicism')
for i, c in enumerate(concepts):
    print(f'{i+1}. Text: {c[\"text_overlay\"]} | Color: {c[\"text_color\"]} | Pos: {c[\"text_position\"]}')
    print(f'   Prompt: {c[\"prompt\"][:80]}...')
"
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/aca/agents/thumbnail_artist.py
git commit -m "feat(aca): add Thumbnail Artist agent"
```

---

### Task 5: Wire agents to scheduler

**Files:**
- Modify: `~/Documents/BotProjects/agents/scheduler.py`

- [ ] **Step 1: Add performance tracking to scheduler**

Read `/Users/admin/Documents/BotProjects/agents/scheduler.py` first.

Add import near the top (after existing aca imports):
```python
from aca.agents.performance_analyst import track_videos, generate_weekly_summary, get_underperformers
from aca.agents.seo_agent import suggest_reoptimization
from aca.susi_bridge import send_to_susi
```

Add these jobs after the ACA Brain schedule block:

```python
# ── ACA Agents — Performance Tracking ──────────────────────────────────────
def _track_performance():
    try:
        logger.info("Performance Analyst: daily tracking")
        # Get video IDs from content_plan or a config
        # For now: read from a tracking list file
        tracking_file = Path(__file__).parent.parent / "meta_memory" / "tracked_videos.json"
        if not tracking_file.exists():
            tracking_file.write_text("[]")
            return
        video_ids = json.loads(tracking_file.read_text())
        if not video_ids:
            return
        result = track_videos(video_ids)
        logger.info(f"Performance tracking done: {result['tracked']} videos")
    except Exception as e:
        logger.error(f"Performance tracking failed: {e}")


def _weekly_performance_summary():
    try:
        logger.info("Performance Analyst: weekly summary")
        tracking_file = Path(__file__).parent.parent / "meta_memory" / "tracked_videos.json"
        if not tracking_file.exists():
            return
        video_ids = json.loads(tracking_file.read_text())
        if not video_ids:
            return
        summary = generate_weekly_summary(video_ids)
        send_to_susi(summary)

        # Check for underperformers → suggest SEO reoptimization
        underperformers = get_underperformers(threshold_pct=0.5)
        if underperformers:
            for up in underperformers[:3]:
                suggestion = suggest_reoptimization(
                    up["video_id"], "", "general",
                    up["views"], up["avg_views"],
                )
                if suggestion.get("new_titles"):
                    msg = (
                        f"💡 *SEO Vorschlag für unterperformendes Video:*\n"
                        f"Video: {up['video_id']} ({up['views']:,} Views, avg: {up['avg_views']:,})\n"
                        f"Neue Titel-Ideen:\n"
                        + "\n".join(f"  • {t}" for t in suggestion["new_titles"][:3])
                        + f"\nGrund: {suggestion.get('reason', '?')}"
                    )
                    send_to_susi(msg)

        logger.info("Weekly summary sent")
    except Exception as e:
        logger.error(f"Weekly summary failed: {e}")


schedule.every().day.at("06:00").do(_track_performance)
schedule.every().sunday.at("19:00").do(_weekly_performance_summary)
logger.info("ACA Agent Team scheduled (Performance: daily 06:00, Summary: Sun 19:00)")
```

- [ ] **Step 2: Create tracked_videos.json**

```bash
echo "[]" > ~/Documents/BotProjects/meta_memory/tracked_videos.json
```

- [ ] **Step 3: Restart scheduler**

```bash
launchctl kickstart -k gui/$(id -u)/com.tubeclone.scheduler 2>&1
```

- [ ] **Step 4: Commit**

```bash
cd ~/Documents/BotProjects
git add agents/scheduler.py
git commit -m "feat(aca): wire Performance Analyst + SEO reopt to scheduler"
```

---

### Task 6: Final integration test

- [ ] **Step 1: Test all agents work together**

```bash
cd ~/Documents/BotProjects/agents
python3 -c "
import os
os.environ.setdefault('GEMINI_API_KEY', '$(grep GEMINI_API_KEY /Users/admin/tuby/.env | cut -d= -f2)')

# Test Performance Analyst
from aca.agents.performance_analyst import scrape_video_stats
stats = scrape_video_stats('dQw4w9WgXcQ')
print(f'1. Performance Analyst: {stats.get(\"views\", 0):,} views ✓')

# Test SEO Agent
from aca.agents.seo_agent import scrape_search_suggest, get_competitor_titles
sugg = scrape_search_suggest('stoicism')
titles = get_competitor_titles('stoicism')
print(f'2. SEO Agent: {len(sugg)} suggestions, {len(titles)} competitor titles ✓')

# Test Thumbnail Artist (text overlay only)
from aca.agents.thumbnail_artist import generate_thumbnail_concepts
concepts = generate_thumbnail_concepts('Dark Psychology Tricks', 'psychology')
print(f'3. Thumbnail Artist: {len(concepts)} concepts ✓')

print('\nAll agents operational!')
"
```

- [ ] **Step 2: Final commit**

```bash
cd ~/Documents/BotProjects
git add -A
git commit -m "feat(aca): Agent Team complete — Performance Analyst, SEO Agent, Thumbnail Artist"
```
