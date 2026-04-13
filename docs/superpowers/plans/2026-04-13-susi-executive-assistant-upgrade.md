# Susi Executive Assistant Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Susi with voice memos, web search, file access, and email drafts so Thomas can send a voice memo and Susi handles research, file lookup, and draft creation.

**Architecture:** 4 independent features wired into Susi's existing Brain/Bot/Action architecture. The biggest change is adding a multi-step action loop to Brain so it can chain actions (search → search → draft). Each feature is a new action module + registration in main.py.

**Tech Stack:** python-telegram-bot 21.5, OpenAI Whisper API, Brave Search API, pypdf, IMAP (GMX), Anthropic Claude

**Important context:** Thomas uses **GMX email** (IMAP), not Gmail. Email drafts are created via IMAP APPEND to the Drafts folder. Google OAuth is only used for Calendar (read-only).

---

### Task 1: Voice message handler in core/bot.py

**Files:**
- Modify: `~/virtual-assistant/core/bot.py:196-205` (add handler in `run()`)

- [ ] **Step 1: Add handle_voice method to Bot class**

Add after `handle_document` method (after line 194) in `core/bot.py`:

```python
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)

        if not is_authorized(user_id, self.allowed_ids):
            await update.message.reply_text(
                "Hallo! Ich bin leider nur für bestimmte Personen verfügbar."
            )
            return

        if not self.rate_limiter.check(user_id):
            await update.message.reply_text(
                "Du sendest gerade sehr viele Nachrichten. Warte kurz."
            )
            return

        voice = update.message.voice or update.message.audio
        if not voice:
            return

        # Check duration (max 15 minutes)
        if voice.duration and voice.duration > 900:
            await update.message.reply_text(
                "Die Sprachmemo ist zu lang (max 15 Minuten). "
                "Schick mir bitte eine kürzere."
            )
            return

        await update.message.chat.send_action("typing")
        await update.message.reply_text("Höre zu...")

        try:
            import tempfile
            import openai

            tg_file = await voice.get_file()
            file_bytes = await tg_file.download_as_bytearray()

            # Whisper needs a file on disk, not raw bytes
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(bytes(file_bytes))
                tmp_path = tmp.name

            try:
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                with open(tmp_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="de",
                    )
                text = transcript.text.strip()
            finally:
                os.unlink(tmp_path)

            if not text:
                await update.message.reply_text(
                    "Ich konnte nichts verstehen. Versuch's nochmal."
                )
                return

            logger.info(f"Voice transcribed ({voice.duration}s): {text[:80]}...")

            # Process transcribed text like any message
            response = await self.brain.process(text, user_id)
        except Exception as e:
            logger.error(f"Voice error: {e}")
            response = (
                "Ich konnte die Sprachmemo nicht verarbeiten. "
                "Versuch's nochmal oder schick mir einen Text."
            )

        # Split long responses
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
```

- [ ] **Step 2: Register voice handler in run()**

In `run()` method (line 196), add after the Document handler registration (line 203):

```python
        self._app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice)
        )
```

- [ ] **Step 3: Add os import if missing**

Check line 1 of bot.py — `os` is already imported. Good.

- [ ] **Step 4: Test voice handler**

Send a voice memo to Susi via Telegram. Expected: "Höre zu..." → transcribed text → Susi responds.

- [ ] **Step 5: Commit**

```bash
cd ~/virtual-assistant
git add core/bot.py
git commit -m "feat: add voice message handler with Whisper transcription"
```

---

### Task 2: Multi-step action loop in core/brain.py

**Files:**
- Modify: `~/virtual-assistant/core/brain.py:241-315`

This is the most significant change. Currently `process()` calls Claude once, extracts one action, executes it, returns. We need a loop that feeds action results back to Claude for follow-up actions.

- [ ] **Step 1: Replace process() method**

Replace the `process` method (lines 241-262) in `core/brain.py`:

```python
    async def process(self, message: str, user_id: str) -> str:
        history = self.memory.get_history(user_id)
        history.append({"role": "user", "content": message})

        max_iterations = 3
        for iteration in range(max_iterations + 1):
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=self._build_system_prompt(user_id, message=message),
                messages=history[-20:],
            )

            self._log_cost(response)
            reply = response.content[0].text.strip()

            # Try to find and execute an action
            action_result = await self._try_execute_action(reply, message, user_id)

            if action_result is None:
                # No action — this is the final text response
                self.memory.save(user_id, message, reply)
                await self._auto_learn(message, reply, user_id)
                return reply

            if isinstance(action_result, dict) and action_result.get("type") == "send_file":
                # Special return: file to send via Telegram (handled by Bot)
                self.memory.save(user_id, message, f"[Datei gesendet: {action_result.get('path', '')}]")
                return action_result

            # Action executed — if we haven't hit max iterations, feed result back
            if iteration < max_iterations:
                # Add assistant's action reply + action result to history
                history.append({"role": "assistant", "content": reply})
                history.append({
                    "role": "user",
                    "content": f"[Aktion ausgefuehrt. Ergebnis:]\n{action_result}",
                })
                continue
            else:
                # Max iterations reached — return the last action result
                self.memory.save(user_id, message, action_result)
                await self._auto_learn(message, action_result, user_id)
                return action_result

        # Should not reach here, but just in case
        return "Ich konnte die Anfrage nicht vollständig bearbeiten."
```

- [ ] **Step 2: Update _try_execute_action to NOT save to memory**

The current `_try_execute_action` (lines 264-315) saves to memory and calls auto_learn internally. Now that `process()` handles the loop, `_try_execute_action` should only execute and return the result — memory saving happens in `process()`.

Replace `_try_execute_action` (lines 264-315):

```python
    async def _try_execute_action(self, reply: str, message: str, user_id: str) -> str | dict | None:
        """Extract and execute action JSON from reply. Returns result string, special dict, or None."""
        import re

        # Try to find JSON with "action" key
        json_candidates = []

        # Pattern 1: ```json ... ``` code block
        for m in re.finditer(r'```(?:json)?\s*(\{.*?\})\s*```', reply, re.DOTALL):
            json_candidates.append(m.group(1))

        # Pattern 2: raw JSON starting with {"action"
        for m in re.finditer(r'(\{"action".*?\})', reply, re.DOTALL):
            json_candidates.append(m.group(1))

        # Pattern 3: entire reply is JSON
        if reply.startswith("{"):
            json_candidates.insert(0, reply)

        for candidate in json_candidates:
            try:
                parsed = json.loads(candidate)
                action_name = parsed.get("action")
                if not action_name:
                    continue

                data = parsed.get("data", {})
                action = self.actions.get(action_name)
                if not action:
                    return f"Aktion '{action_name}' ist nicht verfuegbar."

                data["user_id"] = user_id
                result = await action.handler(data)
                self.memory.log_action(user_id, action_name, data)

                # If there was text before/after the JSON, prepend it
                text_parts = reply.replace(candidate, "").strip()
                text_parts = re.sub(r'```json\s*```', '', text_parts).strip()
                if text_parts and isinstance(result, str):
                    return f"{text_parts}\n\n{result}"
                return result
            except (json.JSONDecodeError, KeyError):
                continue

        return None
```

- [ ] **Step 3: Update Bot.handle_message to handle file_send returns**

In `core/bot.py`, update `handle_message` (around line 96):

```python
        try:
            response = await self.brain.process(text, user_id)
        except Exception as e:
            logger.error(f"Brain error: {e}")
            response = (
                "Ich hab gerade ein technisches Problem, "
                "versuch's in ein paar Minuten nochmal."
            )

        # Handle special return types
        if isinstance(response, dict) and response.get("type") == "send_file":
            file_path = response.get("path", "")
            try:
                await update.message.reply_document(
                    document=open(file_path, "rb"),
                    filename=os.path.basename(file_path),
                )
            except Exception as e:
                logger.error(f"File send error: {e}")
                await update.message.reply_text(f"Konnte Datei nicht senden: {e}")
            return

        await update.message.reply_text(response)
```

Also update `handle_voice` in the same way — after `response = await self.brain.process(text, user_id)`, add the same dict check before the text reply loop.

- [ ] **Step 4: Verify syntax**

Run: `cd ~/virtual-assistant && python -m py_compile core/brain.py && python -m py_compile core/bot.py && echo "OK"`
Expected: "OK"

- [ ] **Step 5: Commit**

```bash
cd ~/virtual-assistant
git add core/brain.py core/bot.py
git commit -m "feat: add multi-step action loop to Brain (max 3 iterations)"
```

---

### Task 3: Web search action (Brave Search API)

**Files:**
- Create: `~/virtual-assistant/susi/actions/web_search.py`

- [ ] **Step 1: Create web_search action**

```python
# ~/virtual-assistant/susi/actions/web_search.py
"""Web search via Brave Search API."""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


async def _web_search(data: dict) -> str:
    """Search the web and return formatted results."""
    query = data.get("query", "").strip()
    if not query:
        return "Ich brauch einen Suchbegriff."

    if not BRAVE_API_KEY:
        return "Web-Suche nicht konfiguriert (BRAVE_SEARCH_API_KEY fehlt)."

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BRAVE_SEARCH_URL,
                params={
                    "q": query,
                    "search_lang": "de",
                    "country": "AT",
                    "count": 5,
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
            )

            if resp.status_code != 200:
                return f"Suche fehlgeschlagen (HTTP {resp.status_code})"

            results = resp.json()
            web_results = results.get("web", {}).get("results", [])

            if not web_results:
                return f"Keine Ergebnisse fuer '{query}'."

            lines = [f"Suchergebnisse fuer '{query}':\n"]
            for i, r in enumerate(web_results[:5], 1):
                title = r.get("title", "?")
                url = r.get("url", "")
                desc = r.get("description", "")
                lines.append(f"{i}. {title}")
                if desc:
                    lines.append(f"   {desc}")
                lines.append(f"   {url}\n")

            return "\n".join(lines)

    except httpx.ConnectError:
        return "Brave Search nicht erreichbar."
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Suche fehlgeschlagen: {e}"


ACTIONS = [
    {
        "name": "web_search",
        "description": "Im Web suchen. Nutze das wenn du aktuelle Infos brauchst (Adressen, Termine, Fakten) oder wenn der User 'such mal' sagt. Du kannst mehrere Suchen hintereinander machen.",
        "parameters": {"query": "string (Suchbegriff)"},
        "handler": _web_search,
    },
]


def register() -> list[dict]:
    return ACTIONS
```

- [ ] **Step 2: Register in main.py**

In `susi/main.py`, add import after line 32:

```python
from susi.actions import web_search
```

Add `web_search` to the `susi_only` list in `register_actions()`:

```python
    susi_only = [projects, ideas, claudia_bridge, email_sync, web_search]
```

- [ ] **Step 3: Add to config.yaml permissions**

In `susi/config.yaml`, add `web_search` to `allowed_without_asking` list.

- [ ] **Step 4: Add BRAVE_SEARCH_API_KEY to .env**

Append to `~/virtual-assistant/.env`:

```
BRAVE_SEARCH_API_KEY=
```

(Thomas fills in the key later from https://api.search.brave.com/app/keys)

- [ ] **Step 5: Test**

Run: `cd ~/virtual-assistant && python -m py_compile susi/actions/web_search.py && echo "OK"`

- [ ] **Step 6: Commit**

```bash
cd ~/virtual-assistant
git add susi/actions/web_search.py susi/main.py susi/config.yaml .env
git commit -m "feat: add web search action via Brave Search API"
```

---

### Task 4: Setup ~/Susi/ folder + symlinks

**Files:**
- Create: `~/virtual-assistant/scripts/setup_susi_folder.sh`

- [ ] **Step 1: Create setup script**

```bash
#!/bin/bash
# Setup ~/Susi/ folder with symlinks to relevant directories

SUSI_DIR="$HOME/Susi"

echo "Setting up Susi folder at $SUSI_DIR..."

mkdir -p "$SUSI_DIR/persoenlich"

# Symlink known directories (only if target exists)
if [ -d "$HOME/Documents/Businessplan" ]; then
    ln -sfn "$HOME/Documents/Businessplan" "$SUSI_DIR/businessplan"
    echo "  Linked: businessplan → ~/Documents/Businessplan"
fi

if [ -d "$HOME/Documents/BotProjects/docs" ]; then
    ln -sfn "$HOME/Documents/BotProjects/docs" "$SUSI_DIR/specs"
    echo "  Linked: specs → ~/Documents/BotProjects/docs"
fi

if [ -d "$HOME/Documents/BotProjects/sops" ]; then
    ln -sfn "$HOME/Documents/BotProjects/sops" "$SUSI_DIR/sops"
    echo "  Linked: sops → ~/Documents/BotProjects/sops"
fi

echo ""
echo "Susi folder ready at $SUSI_DIR"
echo "Lege Dateien in $SUSI_DIR ab die Susi kennen soll."
ls -la "$SUSI_DIR"
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x ~/virtual-assistant/scripts/setup_susi_folder.sh
~/virtual-assistant/scripts/setup_susi_folder.sh
```

Expected: Directory created with symlinks.

- [ ] **Step 3: Verify**

```bash
ls -la ~/Susi/
```

Expected: businessplan, specs, sops symlinks + persoenlich folder.

- [ ] **Step 4: Commit**

```bash
cd ~/virtual-assistant
git add scripts/setup_susi_folder.sh
git commit -m "feat: add setup script for ~/Susi/ folder with symlinks"
```

---

### Task 5: File access actions (search, send, ingest)

**Files:**
- Create: `~/virtual-assistant/susi/actions/file_access.py`

- [ ] **Step 1: Create file access module**

```python
# ~/virtual-assistant/susi/actions/file_access.py
"""File access actions — search, send, and ingest files from ~/Susi/."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SUSI_DIR = Path.home() / "Susi"

# Allowlist: resolved real paths that are OK to access
ALLOWED_ROOTS = [
    str(Path.home() / "Susi"),
    str(Path.home() / "Documents" / "Businessplan"),
    str(Path.home() / "Documents" / "BotProjects" / "docs"),
    str(Path.home() / "Documents" / "BotProjects" / "sops"),
]


def _is_safe_path(filepath: str) -> bool:
    """Check that resolved path is within allowed directories."""
    real = os.path.realpath(filepath)
    return any(real.startswith(root) for root in ALLOWED_ROOTS)


def _fuzzy_match(query: str, filename: str) -> bool:
    """Simple fuzzy match: all query words appear in filename (case-insensitive)."""
    q_lower = query.lower()
    f_lower = filename.lower()
    return all(word in f_lower for word in q_lower.split())


async def _file_search(data: dict) -> str:
    """Search ~/Susi/ for files matching a query."""
    query = data.get("query", "").strip()
    if not query:
        return "Ich brauch einen Suchbegriff fuer die Dateisuche."

    if not SUSI_DIR.exists():
        return "Der Susi-Ordner (~/Susi/) existiert nicht. Bitte zuerst einrichten."

    matches = []
    for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
        for fname in files:
            if fname.startswith("."):
                continue
            full_path = os.path.join(root, fname)
            if not _is_safe_path(full_path):
                continue
            if _fuzzy_match(query, fname):
                rel = os.path.relpath(full_path, str(SUSI_DIR))
                stat = os.stat(full_path)
                size_kb = stat.st_size / 1024
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y")
                matches.append({
                    "name": fname,
                    "path": rel,
                    "full_path": full_path,
                    "size": f"{size_kb:.0f} KB",
                    "modified": modified,
                })

    if not matches:
        return f"Keine Dateien gefunden fuer '{query}' in ~/Susi/."

    # Sort by relevance (shorter filename = better match)
    matches.sort(key=lambda m: len(m["name"]))

    lines = [f"Gefunden ({len(matches)} Dateien):\n"]
    for m in matches[:10]:
        lines.append(f"  {m['path']} ({m['size']}, {m['modified']})")

    return "\n".join(lines)


async def _file_send(data: dict) -> str | dict:
    """Send a file from ~/Susi/ as Telegram document."""
    filename = data.get("filename", "").strip()
    if not filename:
        return "Welche Datei soll ich senden?"

    # Try exact path first, then search
    full_path = str(SUSI_DIR / filename)
    if not os.path.isfile(full_path):
        # Search for it
        search_result = await _file_search({"query": filename, "user_id": data.get("user_id", "")})
        if "Keine Dateien" in search_result:
            return search_result
        # Take first match — parse from search result
        for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
            for fname in files:
                if _fuzzy_match(filename, fname):
                    full_path = os.path.join(root, fname)
                    break

    if not os.path.isfile(full_path):
        return f"Datei nicht gefunden: {filename}"

    if not _is_safe_path(full_path):
        return "Zugriff auf diese Datei ist nicht erlaubt."

    size_mb = os.path.getsize(full_path) / (1024 * 1024)
    if size_mb > 50:
        return f"Datei ist zu gross ({size_mb:.1f} MB, max 50 MB)."

    # Return special dict — Bot handles the actual send
    return {"type": "send_file", "path": full_path}


ACTIONS = [
    {
        "name": "file_search",
        "description": "Dateien in ~/Susi/ suchen. Nutze das wenn Thomas nach einem Dokument fragt.",
        "parameters": {"query": "string (Suchbegriff, z.B. 'Businessplan' oder 'Lebenslauf')"},
        "handler": _file_search,
    },
    {
        "name": "file_send",
        "description": "Datei aus ~/Susi/ als Telegram-Dokument an Thomas senden.",
        "parameters": {"filename": "string (Dateiname oder Pfad in ~/Susi/)"},
        "handler": _file_send,
    },
]


def register() -> list[dict]:
    return ACTIONS
```

- [ ] **Step 2: Register in main.py**

In `susi/main.py`, add import:

```python
from susi.actions import file_access
```

Add to `susi_only` list:

```python
    susi_only = [projects, ideas, claudia_bridge, email_sync, web_search, file_access]
```

- [ ] **Step 3: Add to config.yaml permissions**

Add `file_search` and `file_send` to `allowed_without_asking`.

- [ ] **Step 4: Verify syntax**

Run: `cd ~/virtual-assistant && python -m py_compile susi/actions/file_access.py && echo "OK"`

- [ ] **Step 5: Commit**

```bash
cd ~/virtual-assistant
git add susi/actions/file_access.py susi/main.py susi/config.yaml
git commit -m "feat: add file search and send actions for ~/Susi/ folder"
```

---

### Task 6: File ingestion into Knowledge Store

**Files:**
- Create: `~/virtual-assistant/susi/actions/file_ingestion.py`

- [ ] **Step 1: Create file ingestion module**

```python
# ~/virtual-assistant/susi/actions/file_ingestion.py
"""Ingest documents from ~/Susi/ into Supabase Knowledge Store."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SUSI_DIR = Path.home() / "Susi"
MANIFEST_FILE = SUSI_DIR / ".file_manifest.json"

# Max file size for ingestion (10MB)
MAX_INGEST_SIZE = 10 * 1024 * 1024

# Supported file types
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".csv"}

# Chunk settings
CHUNK_SIZE = 500  # words
CHUNK_OVERLAP = 50  # words


def _load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_manifest(manifest: dict):
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _extract_text(filepath: str) -> str:
    """Extract text from a file based on extension."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except Exception as e:
            logger.error(f"PDF extraction failed for {filepath}: {e}")
            return ""

    elif ext in (".txt", ".md", ".csv", ".html"):
        try:
            text = Path(filepath).read_text(encoding="utf-8", errors="replace")
            if ext == ".html":
                import re
                text = re.sub(r"<[^>]+>", " ", text)
            return text
        except Exception as e:
            logger.error(f"Text extraction failed for {filepath}: {e}")
            return ""

    return ""


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of ~CHUNK_SIZE words."""
    words = text.split()
    if len(words) <= CHUNK_SIZE:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP

    return chunks


async def ingest_all(memory, user_id: str) -> str:
    """Scan ~/Susi/ and ingest new/changed files into Knowledge Store."""
    if not SUSI_DIR.exists():
        return "~/Susi/ existiert nicht."

    manifest = _load_manifest()
    ingested = 0
    skipped = 0
    errors = 0

    for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
        for fname in files:
            if fname.startswith("."):
                continue

            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, str(SUSI_DIR))

            # Check file size
            size = os.path.getsize(full_path)
            if size > MAX_INGEST_SIZE:
                logger.warning(f"Skipping {rel_path}: too large ({size / 1024 / 1024:.1f} MB)")
                skipped += 1
                continue

            # Check if file changed since last ingestion
            modified = os.path.getmtime(full_path)
            modified_str = datetime.fromtimestamp(modified).isoformat()
            prev = manifest.get(rel_path, {})
            if prev.get("modified") == modified_str and prev.get("size") == size:
                skipped += 1
                continue

            # Extract and chunk
            text = _extract_text(full_path)
            if not text:
                errors += 1
                continue

            chunks = _chunk_text(text)
            if not chunks:
                skipped += 1
                continue

            # Delete old chunks for this file
            for i in range(prev.get("chunks", 0)):
                memory.delete_knowledge(user_id, "dokument", f"{rel_path}:chunk_{i}")

            # Store new chunks
            for i, chunk in enumerate(chunks):
                memory.store_knowledge(
                    user_id,
                    "dokument",
                    f"{rel_path}:chunk_{i}",
                    chunk,
                )

            manifest[rel_path] = {
                "modified": modified_str,
                "size": size,
                "chunks": len(chunks),
            }
            ingested += 1
            logger.info(f"Ingested {rel_path}: {len(chunks)} chunks")

    # Clean up manifest entries for deleted files
    for rel_path in list(manifest.keys()):
        full_path = os.path.join(str(SUSI_DIR), rel_path)
        if not os.path.exists(full_path):
            for i in range(manifest[rel_path].get("chunks", 0)):
                memory.delete_knowledge(user_id, "dokument", f"{rel_path}:chunk_{i}")
            del manifest[rel_path]
            logger.info(f"Removed deleted file from knowledge: {rel_path}")

    _save_manifest(manifest)
    return f"Ingestion fertig: {ingested} neu, {skipped} unveraendert, {errors} Fehler."


async def _file_ingest_action(data: dict) -> str:
    """Action handler: ingest a specific file or all files."""
    from core.memory import Memory
    user_id = data.get("user_id", "")
    memory = Memory(bot_name="susi")
    return await ingest_all(memory, user_id)


ACTIONS = [
    {
        "name": "file_ingest",
        "description": "Dateien aus ~/Susi/ einlesen und als Wissen speichern. Nutze das wenn Thomas sagt 'lies die Dateien ein' oder nach dem ersten Setup.",
        "parameters": {},
        "handler": _file_ingest_action,
    },
]


def register() -> list[dict]:
    return ACTIONS
```

- [ ] **Step 2: Register in main.py and add scheduled job**

Add import:

```python
from susi.actions import file_ingestion
```

Add to `susi_only` list:

```python
    susi_only = [projects, ideas, claudia_bridge, email_sync, web_search, file_access, file_ingestion]
```

In `setup_scheduler`, add daily ingestion job:

```python
    async def daily_file_ingestion():
        from susi.actions.file_ingestion import ingest_all
        from core.memory import Memory
        memory = Memory(bot_name="susi")
        for user_id in allowed_ids:
            if not user_id.strip():
                continue
            try:
                result = await ingest_all(memory, user_id.strip())
                logger.info(f"Daily ingestion: {result}")
            except Exception as e:
                logger.error(f"Daily ingestion failed: {e}")

    scheduler.add_cron("file_ingestion", daily_file_ingestion, hour=6, minute=0)
```

- [ ] **Step 3: Check if Memory has delete_knowledge method**

Run: `grep -n "def delete_knowledge" ~/virtual-assistant/core/memory.py`

If it doesn't exist, add it to `core/memory.py`:

```python
    def delete_knowledge(self, user_id: str, category: str, key: str):
        """Delete a knowledge entry."""
        try:
            self.supabase.table("knowledge").delete().eq(
                "user_id", user_id
            ).eq("category", category).eq("key", key).execute()
        except Exception as e:
            logger.warning(f"delete_knowledge failed: {e}")
```

- [ ] **Step 4: Add to config.yaml permissions**

Add `file_ingest` to `allowed_without_asking`.

- [ ] **Step 5: Verify syntax**

Run: `cd ~/virtual-assistant && python -m py_compile susi/actions/file_ingestion.py && echo "OK"`

- [ ] **Step 6: Commit**

```bash
cd ~/virtual-assistant
git add susi/actions/file_ingestion.py susi/main.py susi/config.yaml core/memory.py
git commit -m "feat: add file ingestion into Knowledge Store with daily scheduled scan"
```

---

### Task 7: Email draft action (GMX IMAP)

**Files:**
- Create: `~/virtual-assistant/susi/actions/email_draft.py`
- Modify: `~/virtual-assistant/core/email_reader.py`

**Important:** Thomas uses GMX (IMAP), not Gmail. We create drafts via IMAP APPEND to the Drafts folder.

- [ ] **Step 1: Add create_draft method to EmailReader**

In `core/email_reader.py`, add method to the `EmailReader` class:

```python
    def create_draft(self, to: str, subject: str, body: str, attachments: list[str] = None) -> bool:
        """Create an email draft in GMX Drafts folder via IMAP APPEND."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        import time

        if not self.email_addr or not self.password:
            logger.warning("Email credentials not configured")
            return False

        try:
            # Build MIME message
            if attachments:
                msg = MIMEMultipart()
                msg.attach(MIMEText(body, "plain", "utf-8"))

                for filepath in attachments:
                    if not os.path.isfile(filepath):
                        logger.warning(f"Attachment not found: {filepath}")
                        continue
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={os.path.basename(filepath)}",
                    )
                    msg.attach(part)
            else:
                msg = MIMEText(body, "plain", "utf-8")

            msg["From"] = self.email_addr
            msg["To"] = to
            msg["Subject"] = subject
            msg["Date"] = email.utils.formatdate(localtime=True)

            # Connect and append to Drafts
            mail = imaplib.IMAP4_SSL(self.server, 993)
            mail.login(self.email_addr, self.password)

            # GMX uses "Entwürfe" or "Drafts" — try both
            draft_folder = None
            for folder_name in ["Drafts", "Entw&APw-rfe", "INBOX.Drafts", "INBOX.Entwuerfe"]:
                status, _ = mail.select(folder_name)
                if status == "OK":
                    draft_folder = folder_name
                    break

            if not draft_folder:
                # List all folders to find drafts
                _, folders = mail.list()
                for f in (folders or []):
                    f_str = f.decode() if isinstance(f, bytes) else f
                    if "draft" in f_str.lower() or "entwu" in f_str.lower():
                        # Extract folder name from IMAP response
                        parts = f_str.split('"')
                        if len(parts) >= 4:
                            draft_folder = parts[-2]
                            break

            if not draft_folder:
                logger.error("Could not find Drafts folder on IMAP server")
                mail.logout()
                return False

            mail.select(draft_folder)
            mail.append(
                draft_folder,
                "\\Draft",
                imaplib.Time2Internaldate(time.time()),
                msg.as_bytes(),
            )
            mail.logout()

            logger.info(f"Draft created: To={to}, Subject={subject}")
            return True

        except Exception as e:
            logger.error(f"Draft creation failed: {e}")
            return False
```

- [ ] **Step 2: Create email_draft action**

```python
# ~/virtual-assistant/susi/actions/email_draft.py
"""Email draft action — creates drafts in GMX via IMAP."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SUSI_DIR = Path.home() / "Susi"


async def _email_draft(data: dict) -> str:
    """Create an email draft in Thomas's GMX account."""
    from core.email_reader import EmailReader

    to = data.get("to", "").strip()
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()
    attachment_names = data.get("attachments", [])

    if not to:
        return "Ich brauch eine Empfaenger-Adresse fuer den Entwurf."
    if not subject:
        return "Ich brauch einen Betreff."
    if not body:
        return "Ich brauch den Email-Text."

    # Resolve attachment paths
    attachment_paths = []
    for name in attachment_names:
        full_path = str(SUSI_DIR / name)
        if os.path.isfile(full_path):
            attachment_paths.append(full_path)
        else:
            # Try searching
            for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
                for fname in files:
                    if name.lower() in fname.lower():
                        attachment_paths.append(os.path.join(root, fname))
                        break
                if len(attachment_paths) > len(attachment_names) - 1:
                    break

    reader = EmailReader()
    success = reader.create_draft(to, subject, body, attachment_paths)

    if success:
        att_text = ""
        if attachment_paths:
            att_names = [os.path.basename(p) for p in attachment_paths]
            att_text = f"\nAnhaenge: {', '.join(att_names)}"

        return (
            f"Email-Entwurf erstellt!\n"
            f"Empfaenger: {to}\n"
            f"Betreff: {subject}{att_text}\n\n"
            f"Oeffne dein Email-Programm um den Entwurf zu pruefen und abzusenden."
        )
    else:
        return "Konnte den Entwurf nicht erstellen. Sind die Email-Zugangsdaten korrekt?"


ACTIONS = [
    {
        "name": "email_draft",
        "description": "Email-Entwurf erstellen. Erstellt einen Entwurf im Email-Postfach den Thomas nur noch absenden muss. IMMER zuerst Thomas fragen bevor du den Entwurf erstellst.",
        "parameters": {
            "to": "string (Empfaenger Email-Adresse)",
            "subject": "string (Betreff)",
            "body": "string (Email-Text, professionell, deutsch)",
            "attachments": "list of strings (Dateinamen aus ~/Susi/, optional)",
        },
        "handler": _email_draft,
    },
]


def register() -> list[dict]:
    return ACTIONS
```

- [ ] **Step 3: Register in main.py**

Add import:

```python
from susi.actions import email_draft
```

Add to `susi_only` list:

```python
    susi_only = [projects, ideas, claudia_bridge, email_sync, web_search, file_access, file_ingestion, email_draft]
```

- [ ] **Step 4: Add to config.yaml permissions**

Add `email_draft` to `requires_confirmation` list.

- [ ] **Step 5: Verify syntax**

Run: `cd ~/virtual-assistant && python -m py_compile susi/actions/email_draft.py && python -m py_compile core/email_reader.py && echo "OK"`

- [ ] **Step 6: Commit**

```bash
cd ~/virtual-assistant
git add susi/actions/email_draft.py core/email_reader.py susi/main.py susi/config.yaml
git commit -m "feat: add email draft action via GMX IMAP"
```

---

### Task 8: Integration test — end-to-end

**Files:** None new — testing everything together

- [ ] **Step 1: Verify all files compile**

```bash
cd ~/virtual-assistant
python -m py_compile core/bot.py
python -m py_compile core/brain.py
python -m py_compile core/email_reader.py
python -m py_compile susi/main.py
python -m py_compile susi/actions/web_search.py
python -m py_compile susi/actions/file_access.py
python -m py_compile susi/actions/file_ingestion.py
python -m py_compile susi/actions/email_draft.py
echo "All OK"
```

- [ ] **Step 2: Verify ~/Susi/ folder exists**

```bash
ls -la ~/Susi/
```

- [ ] **Step 3: Run initial file ingestion manually**

```bash
cd ~/virtual-assistant && source venv/bin/activate
python -c "
import asyncio
from susi.actions.file_ingestion import ingest_all
from core.memory import Memory
async def main():
    m = Memory(bot_name='susi')
    result = await ingest_all(m, '<THOMAS_USER_ID>')
    print(result)
asyncio.run(main())
"
```

Expected: Files ingested from ~/Susi/ into Knowledge Store.

- [ ] **Step 4: Restart Susi**

Kill old process, start new:
```bash
pkill -f "susi.main"; sleep 3
cd ~/virtual-assistant && source venv/bin/activate
nohup python -m susi.main > /tmp/susi.log 2>&1 &
sleep 5 && tail -5 /tmp/susi.log
```

Expected: All handlers registered, scheduler started, no errors.

- [ ] **Step 5: Test voice memo**

Send a short voice memo to Susi via Telegram. Expected: "Höre zu..." → transcription → normal response.

- [ ] **Step 6: Test web search**

Send: "Such mal nach AMS Wien UGP Infotag"
Expected: Susi returns web search results about AMS UGP.

- [ ] **Step 7: Test file search and send**

Send: "Hast du den Businessplan?"
Expected: Susi finds the file in ~/Susi/ and sends it or lists it.

Send: "Schick mir den Businessplan"
Expected: Susi sends the PDF as Telegram document.

- [ ] **Step 8: Test email draft (full flow)**

Send voice memo: "Schreib eine Email ans AMS wegen dem UGP Infotag, ich will mich anmelden"
Expected: Susi asks for confirmation → researches AMS UGP → creates draft in GMX → confirms.

- [ ] **Step 9: Commit any fixes**

```bash
cd ~/virtual-assistant
git add -A
git commit -m "fix: integration test fixes for executive assistant upgrade"
```
