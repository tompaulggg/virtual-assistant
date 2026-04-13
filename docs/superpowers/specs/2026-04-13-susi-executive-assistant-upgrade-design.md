# Susi Executive Assistant Upgrade — Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Scope:** 4 new capabilities for Susi

## Overview

Upgrade Susi from a text-only project tracker to a full executive assistant that can receive voice memos, research the web, access files, and prepare email drafts. Thomas should be able to send a voice memo saying "Schreib eine Email ans AMS wegen UGP Infotag" and Susi handles the rest: transcribes, researches, drafts, attaches documents, creates a Gmail draft ready to send.

## Feature 1: Sprachmemos

### What it does

Thomas sends a voice memo via Telegram. Susi transcribes it and processes it like any text message.

### Technical

- New handler in `core/bot.py`: `handle_voice`
- Registered via `MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice)`
- Downloads .ogg file from Telegram via `voice.get_file()` + `download_as_bytearray()`
- Saves to temp file (`tempfile.NamedTemporaryFile(suffix=".ogg")`) — Whisper API needs a file handle, not raw bytes
- Sends to OpenAI Whisper API: `openai.audio.transcriptions.create(model="whisper-1", file=temp_file, language="de")`
- Temp file deleted after transcription
- `language="de"` hint for better German/Denglisch transcription
- Transcribed text goes to `brain.process()` — same as any text message
- Max duration: 15 minutes. Longer memos get a friendly rejection message.
- Whisper API limit: 25MB per file. 15min .ogg is ~2.5MB — well within limit.

### Cost

~$0.006/minute. A 2-minute memo costs $0.012. Negligible.

### Dependencies

- `OPENAI_API_KEY` in `.env` (already present)
- `openai` Python package (already installed)

### Files

- Modify: `core/bot.py` — add `handle_voice` method + register handler in `run()`

## Feature 2: Web-Recherche (Brave Search API)

### What it does

Susi can search the web to find current information. Works two ways:
1. **On command:** Thomas says "such mal nach AMS UGP Infotag" → Susi searches
2. **Automatic:** When drafting emails or answering questions where she's unsure, Susi searches proactively (up to 3 searches per request)

### Technical

- New action: `web_search` in `susi/actions/web_search.py`
- Brave Search API with `search_lang=de`, `country=AT` (Austrian results)
- Returns top 5 results with title, URL, description snippet
- Results are formatted as context text for Brain
- Brain can call `web_search` multiple times (max 3 per request) for multi-step research

### Multi-Step Research

Brain currently executes ONE action per message and returns. For web search and email drafting, Brain needs a **multi-step action loop**: execute an action, feed the result back to Claude as context, let Claude decide the next action, repeat up to 3 times.

**Change to `core/brain.py`:** Add a loop in `process()`:
1. Call Claude → get response
2. If response contains an action → execute it
3. Feed action result back as a new user message: "Action result: {result}"
4. Call Claude again (with action result in context)
5. Repeat up to 3 iterations, then force a final text response
6. If response contains no action → return text as normal

This is the most significant architectural change in this spec.

### Knowledge Integration

Search results that contain important facts (dates, addresses, deadlines) are automatically saved via the existing auto-learning system. Brain's Haiku-based fact extraction runs on the combined response, so researched facts end up in the Knowledge Store.

### Cost

Brave Search API: $5/1,000 queries. Free tier gives $5/month credit (~1,000 searches). At 50-100 searches/day, costs $7.50-15/month.

### Dependencies

- `BRAVE_SEARCH_API_KEY` in `.env` (new)
- `httpx` (already installed)

### Files

- Create: `susi/actions/web_search.py` — action + Brave API integration
- Modify: `susi/config.yaml` — add `web_search` to `allowed_without_asking`

## Feature 3: Datei-Zugriff + Knowledge Ingestion

### What it does

Susi has her own folder (`~/Susi/`) with symlinks to relevant directories. She can search files, send them via Telegram, attach them to Gmail drafts, and ingest their contents into the Knowledge Store for semantic search.

### Folder Structure

```
~/Susi/
  businessplan/  → ~/Documents/Businessplan/
  specs/         → ~/Documents/BotProjects/docs/
  sops/          → ~/Documents/BotProjects/sops/
  persoenlich/   (own folder for CVs, personal docs)
```

The initial setup script creates the directory, symlinks, and runs first ingestion.

### Actions

**`file_search`** — Search `~/Susi/` by filename (fuzzy match)
- Parameter: `query` (string)
- Returns: list of matching files with name, path, size, modified date
- Uses `glob` + fuzzy string matching on filenames

**`file_send`** — Send file as Telegram document
- Parameter: `filename` (string)
- Finds file via `file_search`, sends via Telegram bot
- Only files within allowed directories
- **Implementation note:** Actions don't have direct bot access. `file_send` returns a special dict `{"type": "send_file", "path": "/abs/path"}` instead of a string. Brain/Bot recognizes this return type and calls `bot.send_document()`. Same pattern as `claudia_bridge.set_telegram_bot()`.

**`file_ingest`** — Read document and store as Knowledge
- Parameter: `filename` (string, optional — if omitted, ingests all new/changed files)
- PDFs via `pypdf` (already installed), MD/TXT read directly
- Content split into chunks (~500 words, 50 word overlap)
- Each chunk stored in Supabase `knowledge` table with embedding
- Category: `dokument`, Key: `{filename}:chunk_{n}`, Value: chunk text

### Scheduled Ingestion

Daily job at 06:00: scans `~/Susi/` for new or modified files (tracked via `modified_time` + `file_size` hash stored in a local JSON manifest). Changed files are re-ingested. Deleted files have their knowledge entries removed.

Manifest file: `~/Susi/.file_manifest.json`

```json
{
  "businessplan/TubeClone_Businessplan.pdf": {
    "modified": "2026-04-10T14:30:00",
    "size": 245000,
    "chunks": 12
  }
}
```

### Security

- All file operations validate path with `os.path.realpath()`
- Resolved path must be within an allowlist of directories:
  - `~/Susi/` itself
  - All symlink targets (`~/Documents/Businessplan/`, `~/Documents/BotProjects/docs/`, `~/Documents/BotProjects/sops/`)
- No symlinks to locations outside the allowlist
- Max file size for Telegram send: 50MB
- Max file size for ingestion: 10MB (larger files skipped with warning)

### Dependencies

- `pypdf` (already installed)
- Supabase Knowledge Store (already exists)

### Files

- Create: `susi/actions/file_access.py` — file_search, file_send, file_ingest actions
- Create: `susi/actions/file_ingestion.py` — chunking logic, manifest tracking, scheduled scan
- Create: `scripts/setup_susi_folder.sh` — one-time setup script for ~/Susi/ + symlinks
- Modify: `susi/main.py` — register file actions + daily ingestion job
- Modify: `susi/config.yaml` — add file actions to permissions

## Feature 4: Email-Entwurf (Gmail Draft)

### What it does

Susi prepares email drafts in Thomas's Gmail. Thomas opens Gmail, reviews the draft, and clicks Send. Susi does NOT send emails directly.

### Flow

1. Thomas: "Schreib eine Email ans AMS wegen UGP Infotag"
2. Susi researches (automatic web_search for AMS contact, UGP details, Infotag dates)
3. Susi corrects Thomas if needed ("Der naechste Infotag ist am 15. Mai, nicht April")
4. Susi creates Gmail Draft via API with:
   - Empfaenger (researched or from Knowledge)
   - Betreff
   - Professioneller Email-Text (deutsch)
   - Attachments from `~/Susi/` if requested
5. Susi confirms: "Email-Entwurf erstellt. Empfaenger: ams@wien.gv.at, Betreff: 'Anmeldung UGP Infotag'. Oeffne Gmail um zu pruefen und abzusenden."

### Technical

- New action: `email_draft` in `susi/actions/email_draft.py`
- Gmail API `drafts.create()` with MIME message construction
- Attachments: read file from `~/Susi/`, encode as base64, add as MIME part
- Scope upgrade: add `https://www.googleapis.com/auth/gmail.compose` to existing Gmail OAuth

### Action Parameters

```
email_draft:
  to: string (email address)
  subject: string
  body: string (the email text)
  attachments: list of strings (filenames from ~/Susi/, optional)
```

### Smart Drafting

When Brain decides to create an email draft, it follows this sequence:
1. If no recipient email → `web_search` to find it
2. If topic needs current info → `web_search` for details
3. If Thomas said something incorrect → Susi corrects in her response
4. If attachments mentioned → `file_search` to find the file
5. Create draft with all gathered info

This is handled by Brain's existing sequential action loop — no new orchestration needed.

### Dependencies

- Gmail API (already integrated for reading)
- OAuth scope upgrade: `gmail.compose` (requires re-auth once — see Setup below)
- `email.mime` (Python stdlib)

### Gmail OAuth Setup (one-time)

Adding `gmail.compose` scope requires Thomas to re-authorize once:
1. Delete existing token file (`~/.google/token_susi.json` or wherever stored)
2. Restart Susi → Gmail OAuth flow triggers automatically
3. Thomas clicks the auth URL, grants "compose" permission
4. New token saved with both read + compose scopes
5. This is a one-time step, documented in setup instructions

### Files

- Create: `susi/actions/email_draft.py` — draft creation + MIME attachment handling
- Modify: `core/email_reader.py` — add `create_draft()` method, upgrade OAuth scopes
- Modify: `susi/config.yaml` — add `email_draft` to `requires_confirmation`

### Permission

`email_draft` requires confirmation — Susi must ask Thomas before creating the draft. This prevents accidental drafts from misunderstood voice memos.

## Files Summary

### New Files

| File | Purpose |
|------|---------|
| `susi/actions/web_search.py` | Brave Search API integration + action |
| `susi/actions/file_access.py` | file_search, file_send, file_ingest actions |
| `susi/actions/file_ingestion.py` | Chunking, manifest tracking, scheduled scan |
| `susi/actions/email_draft.py` | Gmail Draft creation + MIME attachments |
| `scripts/setup_susi_folder.sh` | One-time ~/Susi/ folder + symlinks setup |

### Modified Files

| File | Change |
|------|--------|
| `core/bot.py` | Add voice message handler + file_send return type handling |
| `core/brain.py` | Add multi-step action loop (max 3 iterations) |
| `core/email_reader.py` | Add create_draft(), upgrade OAuth scopes |
| `susi/main.py` | Register new actions + file ingestion job |
| `susi/config.yaml` | Add new actions to permissions |
| `.env` | Add BRAVE_SEARCH_API_KEY |

## Out of Scope

- Email **senden** (nur Drafts) — kommt spaeter
- Kalender schreiben — eigener Spec
- Multi-User Support — nicht noetig (nur Thomas)
- Datei-Upload von Thomas an Susi → ~/Susi/ — nice-to-have fuer spaeter

## Example End-to-End Flow

```
Thomas: (Sprachmemo) "Susi, schreib eine Email ans AMS Wien.
Ich will mich fuer das Unternehmergruendungsprogramm anmelden
und zum naechsten Infotag kommen. Haeng den Businessplan an."

Susi transkribiert → "Susi, schreib eine Email ans AMS Wien..."

Brain erkennt: email_draft Action noetig
  → web_search("AMS Wien UGP Unternehmergruendungsprogramm Kontakt Email")
  → Ergebnis: ams.wien@ams.at, naechster Infotag 15. Mai 2026
  → web_search("AMS UGP Anmeldung Infotag Voraussetzungen")
  → Ergebnis: Online-Anmeldung noetig, Businessplan mitbringen
  → file_search("Businessplan")
  → Ergebnis: ~/Susi/businessplan/TubeClone_Businessplan_v2.pdf
  → email_draft(
      to="ams.wien@ams.at",
      subject="Anmeldung UGP Infotag — Thomas Gaeta",
      body="Sehr geehrte Damen und Herren, ...",
      attachments=["businessplan/TubeClone_Businessplan_v2.pdf"]
    )

Susi an Thomas:
  "Email-Entwurf erstellt!
   Empfaenger: ams.wien@ams.at
   Betreff: Anmeldung UGP Infotag — Thomas Gaeta
   Attachment: TubeClone_Businessplan_v2.pdf

   Uebrigens: Der naechste Infotag ist am 15. Mai.
   Die Online-Anmeldung ist Voraussetzung — soll ich
   den Link raussuchen?

   Oeffne Gmail um den Entwurf zu pruefen und abzusenden."
```
