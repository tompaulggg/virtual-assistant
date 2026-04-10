# SUSI – Persönlicher AI Assistent für Thomas
## Claude Code Implementierungs-Anleitung

> Lies dieses Dokument vollständig bevor du eine einzige Zeile Code schreibst.
> Dann implementiere Schritt für Schritt in der angegebenen Reihenfolge.

---

## Kontext & Ziel

Baue einen persönlichen AI-Assistenten namens **Susi** für Thomas (Wien, EPU, Gründer TubeClone).
Susi läuft 24/7 auf Railway, kommuniziert via Telegram, kennt Thomas vollständig
und handelt proaktiv ohne dass Thomas jeden Schritt anordnen muss.

---

## Projekt-Struktur (genau so anlegen)

```
susi/
├── CLAUDE.md                  ← Susi's Persönlichkeit & Thomas-Kontext
├── PROGRESS.md                ← Fortschritt für neue Claude Code Sessions
├── main.py                    ← Entry Point, Telegram Bot
├── core/
│   ├── brain.py               ← Claude API, Action-Router
│   ├── memory.py              ← Supabase Langzeitgedächtnis
│   └── watcher.py             ← Proaktiver Background-Loop
├── agents/
│   ├── task_agent.py          ← Notion Tasks lesen/schreiben
│   ├── email_agent.py         ← Gmail lesen, Drafts erstellen
│   ├── calendar_agent.py      ← Google Calendar
│   ├── tubeclone_agent.py     ← TubeClone Pipeline Status
│   └── cleanup_agent.py       ← Daten aufräumen, sortieren
├── tools/
│   ├── gmail.py               ← Gmail API Wrapper
│   ├── gcalendar.py           ← Google Calendar API Wrapper
│   └── notion.py              ← Notion API Wrapper
├── .env                       ← Secrets (nie committen)
├── requirements.txt
├── railway.toml               ← Deployment Config
└── Procfile                   ← railway start command
```

---

## Tech Stack

| Was | Tool | Version |
|-----|------|---------|
| AI Core | `anthropic` SDK | latest |
| Telegram | `python-telegram-bot` | 20.x |
| Memory | `supabase` | latest |
| Scheduling | `apscheduler` | 3.x |
| Email | `google-api-python-client` | latest |
| Kalender | `google-api-python-client` | latest |
| Tasks | Notion API via `httpx` | latest |
| Env | `python-dotenv` | latest |
| Hosting | Railway | — |

```bash
# requirements.txt
anthropic
python-telegram-bot==20.7
supabase
apscheduler
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
httpx
python-dotenv
```

---

## Schritt 1 – CLAUDE.md anlegen

```markdown
# SUSI – Persönlicher Assistent von Thomas

## Wer ist Thomas
- Wohnt in Wien 1010
- Gründer TubeClone (AI YouTube Automation SaaS, in Entwicklung)
- Co-Gründer TechLine HiBit KG (tech-line.at)
- EPU mit freiem Gewerbe IT
- Mentor: Niv Baniahmad (EVENOA, Dubai)
- Laufend: Mikrokredit OESB (in Bearbeitung), AMS UGP Antrag

## Projekte die Susi kennt
- TubeClone: 7-Step Pipeline (Scout→Analyst→Writer→Director→Animator→Voice→Editor)
- Claudia: CEO Agent für TubeClone (läuft separat in ~/projects/claudia)
- Susi: Dieses Projekt (persönlicher Assistent)

## Susi's Kommunikationsstil
- Immer auf Deutsch
- Direkt, kein Overhead, keine Füllwörter
- Kurz und präzise – außer Thomas fragt nach Details
- Proaktiv denken: Kontext mitdenken, Folgeprobleme antizipieren

## Was Susi DARF (ohne Rückfrage)
- Kalendereinträge erstellen und löschen
- Notion Tasks anlegen, abhaken, priorisieren
- Email-Drafts erstellen
- Erinnerungen setzen
- Informationen recherchieren

## Was Susi NICHT darf (immer erst fragen)
- Emails absenden
- Dateien permanent löschen
- Externe Buchungen oder Käufe tätigen
- Code in Produktion deployen

## Offene Prioritäten Thomas (Stand heute)
1. TubeClone: Pipeline-Code fertigstellen
2. Mikrokredit OESB: Status wöchentlich nachfragen
3. AMS UGP: Unterlagen vorbereiten
4. Ersten zahlenden TubeClone-Kunden finden
```

---

## Schritt 2 – Supabase einrichten

Erstelle folgende Tabellen in Supabase:

```sql
-- Konversations-Gedächtnis
CREATE TABLE conversations (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id text NOT NULL,
  role text NOT NULL,           -- 'user' oder 'assistant'
  content text NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Langzeit-Fakten über Thomas
CREATE TABLE memory_facts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  category text NOT NULL,       -- z.B. 'preference', 'project', 'person'
  key text NOT NULL,
  value text NOT NULL,
  updated_at timestamptz DEFAULT now()
);

-- Offene Tasks
CREATE TABLE tasks (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  status text DEFAULT 'open',   -- 'open', 'done', 'snoozed'
  due_date date,
  priority text DEFAULT 'normal',
  created_at timestamptz DEFAULT now()
);
```

---

## Schritt 3 – core/memory.py

```python
from supabase import create_client
import os

class Memory:
    def __init__(self):
        self.db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

    def get_history(self, user_id: str, limit: int = 20) -> list:
        result = self.db.table("conversations") \
            .select("role, content") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return list(reversed([
            {"role": r["role"], "content": r["content"]}
            for r in result.data
        ]))

    def save(self, user_id: str, user_msg: str, assistant_msg: str):
        self.db.table("conversations").insert([
            {"user_id": user_id, "role": "user", "content": user_msg},
            {"user_id": user_id, "role": "assistant", "content": assistant_msg}
        ]).execute()

    def remember_fact(self, category: str, key: str, value: str):
        self.db.table("memory_facts").upsert({
            "category": category, "key": key, "value": value
        }).execute()

    def recall_facts(self, category: str = None) -> list:
        q = self.db.table("memory_facts").select("*")
        if category:
            q = q.eq("category", category)
        return q.execute().data
```

---

## Schritt 4 – core/brain.py

```python
import anthropic
import json
import os
from .memory import Memory

class SusiBrain:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.memory = Memory()
        with open("CLAUDE.md", "r") as f:
            base = f.read()

        self.system = base + """

## Action Protocol
Wenn du eine Aktion ausführen willst, antworte NUR mit validem JSON:

{"action": "create_task",    "data": {"title": "...", "due": "YYYY-MM-DD", "priority": "high|normal|low"}}
{"action": "draft_email",    "data": {"to": "...", "subject": "...", "body": "..."}}
{"action": "create_event",   "data": {"title": "...", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_min": 60}}
{"action": "set_reminder",   "data": {"text": "...", "when": "YYYY-MM-DD HH:MM"}}
{"action": "list_tasks",     "data": {}}
{"action": "tubeclone_status","data": {}}
{"action": "read_emails",    "data": {"max": 5}}
{"action": "cleanup",        "data": {"target": "emails|tasks|calendar"}}
{"action": "remember",       "data": {"category": "...", "key": "...", "value": "..."}}

Für normale Textantworten: einfach Text, kein JSON.
"""

    async def process(self, message: str, user_id: str) -> str:
        history = self.memory.get_history(user_id)
        history.append({"role": "user", "content": message})

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            system=self.system,
            messages=history
        )

        reply = response.content[0].text.strip()

        if reply.startswith("{"):
            try:
                action = json.loads(reply)
                result = await self._execute(action)
                self.memory.save(user_id, message, result)
                return result
            except json.JSONDecodeError:
                pass

        self.memory.save(user_id, message, reply)
        return reply

    async def _execute(self, action: dict) -> str:
        from agents.task_agent import TaskAgent
        from agents.email_agent import EmailAgent
        from agents.calendar_agent import CalendarAgent
        from agents.tubeclone_agent import TubeCloneAgent
        from agents.cleanup_agent import CleanupAgent

        name = action.get("action")
        data = action.get("data", {})

        routes = {
            "create_task":     TaskAgent().create,
            "list_tasks":      TaskAgent().list_open,
            "set_reminder":    TaskAgent().remind,
            "draft_email":     EmailAgent().draft,
            "read_emails":     EmailAgent().read,
            "create_event":    CalendarAgent().create,
            "tubeclone_status":TubeCloneAgent().status,
            "cleanup":         CleanupAgent().run,
            "remember":        lambda d: self.memory.remember_fact(
                                   d["category"], d["key"], d["value"]
                               ) or "✅ Gespeichert.",
        }

        fn = routes.get(name)
        if fn:
            return await fn(data) if callable(fn) else "✅ Erledigt."
        return f"❓ Unbekannte Aktion: {name}"
```

---

## Schritt 5 – main.py (Telegram Bot)

```python
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from core.brain import SusiBrain

load_dotenv()
brain = SusiBrain()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != os.getenv("THOMAS_TELEGRAM_ID"):
        return  # Nur Thomas

    text = update.message.text
    await update.message.chat.send_action("typing")
    response = await brain.process(text, str(update.effective_user.id))
    await update.message.reply_text(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sprachnachrichten: später Whisper API einbauen
    await update.message.reply_text("🎤 Sprachnachrichten kommen in Phase 2!")

def main():
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("🟢 Susi ist online")
    app.run_polling()

if __name__ == "__main__":
    main()
```

---

## Schritt 6 – core/watcher.py (Proaktiver Loop)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.brain import SusiBrain
import os

brain = SusiBrain()
THOMAS_ID = os.getenv("THOMAS_TELEGRAM_ID")

async def morning_brief(bot):
    """Täglich 07:00 – Tagesüberblick"""
    msg = await brain.process(
        "Erstelle einen kurzen Morgen-Brief für Thomas: "
        "Heutige Termine, offene Tasks, was heute wichtig ist.", THOMAS_ID)
    await bot.send_message(chat_id=THOMAS_ID, text=f"☀️ Guten Morgen!\n\n{msg}")

async def evening_review(bot):
    """Täglich 21:00 – Tagesabschluss"""
    msg = await brain.process(
        "Kurzer Tagesabschluss: Was wurde erledigt, was ist für morgen offen?", THOMAS_ID)
    await bot.send_message(chat_id=THOMAS_ID, text=f"🌙 Tagesabschluss\n\n{msg}")

async def mikrokredit_reminder(bot):
    """Jeden Montag – OESB Status"""
    await bot.send_message(chat_id=THOMAS_ID,
        text="📋 Reminder: Hast du diese Woche beim OESB wegen Mikrokredit nachgefragt?")

async def task_check(bot):
    """Alle 2 Stunden – Offene Tasks prüfen"""
    msg = await brain.process("Gibt es Tasks die jetzt automatisch erledigt werden können?", THOMAS_ID)
    if "erledigt" in msg.lower() or "✅" in msg:
        await bot.send_message(chat_id=THOMAS_ID, text=msg)

def start_watcher(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(morning_brief,      'cron', hour=7,  minute=0,  args=[bot])
    scheduler.add_job(evening_review,     'cron', hour=21, minute=0,  args=[bot])
    scheduler.add_job(mikrokredit_reminder,'cron', day_of_week='mon', hour=9, args=[bot])
    scheduler.add_job(task_check,         'interval', hours=2, args=[bot])
    scheduler.start()
    return scheduler
```

---

## Schritt 7 – .env Vorlage

```bash
# Telegram
TELEGRAM_TOKEN=
THOMAS_TELEGRAM_ID=

# Anthropic
ANTHROPIC_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_KEY=

# Google OAuth (für Gmail + Calendar)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=

# Notion
NOTION_TOKEN=
NOTION_DATABASE_ID=
```

---

## Schritt 8 – Railway Deployment

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python main.py"
restartPolicyType = "always"
```

```
# Procfile
worker: python main.py
```

---

## Implementierungs-Reihenfolge für Claude Code

```
1. Projektstruktur anlegen (alle Ordner + leere Dateien)
2. requirements.txt installieren + testen
3. CLAUDE.md mit Thomas-Kontext befüllen
4. Supabase Tabellen erstellen
5. core/memory.py implementieren + testen
6. core/brain.py implementieren
7. main.py – Telegram Bot starten und testen
8. agents/task_agent.py – Notion Integration
9. agents/email_agent.py – Gmail Integration
10. agents/calendar_agent.py – Google Calendar
11. agents/tubeclone_agent.py – TubeClone Status
12. core/watcher.py – Proaktiver Loop
13. Railway Deployment
14. Smoke Test: Alle Features manuell testen
```

---

## PROGRESS.md Template (nach jeder Session aktualisieren)

```markdown
# SUSI PROGRESS

## Zuletzt abgeschlossen
- [ ] Schritt X: ...

## Nächster Schritt
- Schritt Y: ...

## Bekannte Probleme
- ...

## Offene Entscheidungen
- ...
```

---

## Definition of Done

- [ ] Susi antwortet auf Telegram
- [ ] Gedächtnis bleibt nach Neustart erhalten
- [ ] Morning Brief kommt täglich um 07:00
- [ ] Tasks können angelegt und abgehakt werden
- [ ] Gmail Drafts werden erstellt
- [ ] Kalendereinträge funktionieren
- [ ] Läuft auf Railway ohne Manuel eingriff
- [ ] Nur Thomas hat Zugriff
