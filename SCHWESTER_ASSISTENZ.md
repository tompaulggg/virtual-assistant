# LENA – Persönliche AI Assistentin (Einsteigerversion)
## Claude Code Implementierungs-Anleitung

> Lies dieses Dokument vollständig bevor du eine einzige Zeile Code schreibst.
> Dann implementiere Schritt für Schritt in der angegebenen Reihenfolge.

---

## Kontext & Ziel

Baue eine einfache, zuverlässige persönliche AI-Assistentin für
nicht-technische Nutzerinnen. Der Fokus liegt auf:

- **Einfachheit:** Einfach Telegram öffnen und losschreiben
- **Zuverlässigkeit:** Funktioniert immer, keine Fehler, keine Verwirrung
- **Nützlichkeit:** Erledigt die Dinge die täglich Zeit kosten

Der Name **Lena** ist ein Platzhalter – wird beim Setup auf den echten Namen angepasst.

---

## Projekt-Struktur (minimal, bewusst einfach gehalten)

```
lena/
├── CLAUDE.md               ← Lena's Persönlichkeit & Nutzer-Kontext
├── PROGRESS.md
├── main.py                 ← Telegram Bot Entry Point
├── brain.py                ← Claude API + Action Router (alles in einer Datei)
├── memory.py               ← Supabase Gedächtnis
├── actions/
│   ├── reminders.py        ← Erinnerungen setzen
│   ├── shopping.py         ← Einkaufslisten verwalten
│   ├── calendar.py         ← Termine & Kalender
│   └── info.py             ← Infos recherchieren, Fragen beantworten
├── .env
├── requirements.txt
└── railway.toml
```

---

## Tech Stack (minimal)

| Was | Tool |
|-----|------|
| AI | `anthropic` claude-sonnet-4-5 (günstiger als Opus, reicht hier) |
| Interface | `python-telegram-bot` 20.x |
| Gedächtnis | `supabase` (kostenloser Free Tier reicht) |
| Erinnerungen | `apscheduler` |
| Hosting | Railway (~€5/Monat) |

```
# requirements.txt
anthropic
python-telegram-bot==20.7
supabase
apscheduler
python-dotenv
httpx
```

---

## Schritt 1 – CLAUDE.md anlegen

Dieses File wird bei jedem Setup auf die Person angepasst.
Vorlage:

```markdown
# LENA – Persönliche Assistentin

## Über [Name der Nutzerin]
- Name: [Vorname]
- Wohnort: [Stadt]
- Beruf: [Beruf]
- Wichtige Menschen: [Familie, Freunde]
- Gewohnheiten: [Morgenroutine, Sport, etc.]

## Lena's Kommunikationsstil
- Freundlich und warm, wie eine gute Freundin
- Immer auf Deutsch
- Kurze, klare Antworten
- Kein Technik-Jargon
- Wenn etwas nicht klar ist: einfach nachfragen

## Was Lena DARF (ohne Rückfrage)
- Erinnerungen setzen
- Einkaufsliste ergänzen oder zeigen
- Kalendereinträge erstellen
- Infos recherchieren und zusammenfassen
- Fragen beantworten

## Was Lena NICHT darf (immer erst fragen)
- Emails versenden
- Einkäufe tätigen
- Termine absagen

## Aktuelle Themen die Lena kennt
(hier eintippen was gerade wichtig ist im Leben der Nutzerin)
- ...
```

---

## Schritt 2 – Supabase einrichten

Nur zwei Tabellen – so einfach wie möglich:

```sql
-- Gesprächsverlauf
CREATE TABLE conversations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Erinnerungen
CREATE TABLE reminders (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    text text NOT NULL,
    remind_at timestamptz NOT NULL,
    sent boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

-- Einkaufslisten
CREATE TABLE shopping_lists (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    item text NOT NULL,
    done boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);
```

---

## Schritt 3 – brain.py (alles in einer Datei)

```python
import anthropic
import json
import os
from memory import Memory

class LenaBrain:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.memory = Memory()

        with open("CLAUDE.md", "r") as f:
            base = f.read()

        self.system = base + """

## Was du tun kannst
Wenn du eine Aktion ausführen willst, antworte NUR mit JSON (kein Text drum herum):

Erinnerung setzen:
{"action": "remind", "text": "...", "when": "YYYY-MM-DDTHH:MM"}

Einkauf hinzufügen:
{"action": "shopping_add", "items": ["Milch", "Brot"]}

Einkaufsliste zeigen:
{"action": "shopping_list"}

Einkauf abhaken:
{"action": "shopping_done", "item": "Milch"}

Termin erstellen:
{"action": "create_event", "title": "...", "date": "YYYY-MM-DD", "time": "HH:MM"}

Für alles andere: einfach normal antworten, kein JSON.
"""

    async def process(self, message: str, user_id: str) -> str:
        history = self.memory.get_history(user_id)
        history.append({"role": "user", "content": message})

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=self.system,
            messages=history[-15:]
        )

        reply = response.content[0].text.strip()

        # Action ausführen
        if reply.startswith("{"):
            try:
                action = json.loads(reply)
                result = await self._run_action(action, user_id)
                self.memory.save(user_id, message, result)
                return result
            except json.JSONDecodeError:
                pass

        self.memory.save(user_id, message, reply)
        return reply

    async def _run_action(self, action: dict, user_id: str) -> str:
        from actions.reminders import add_reminder
        from actions.shopping import add_items, get_list, mark_done
        from actions.calendar import create_event

        name = action.get("action")

        if name == "remind":
            return await add_reminder(user_id, action["text"], action["when"])

        elif name == "shopping_add":
            return await add_items(user_id, action["items"])

        elif name == "shopping_list":
            return await get_list(user_id)

        elif name == "shopping_done":
            return await mark_done(user_id, action["item"])

        elif name == "create_event":
            return await create_event(
                action["title"], action["date"], action.get("time", "")
            )

        return "✅ Erledigt!"
```

---

## Schritt 4 – main.py

```python
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from brain import LenaBrain

load_dotenv()
brain = LenaBrain()

# Erlaubte User IDs (kann mehrere haben)
ALLOWED_USERS = os.getenv("ALLOWED_USER_IDS", "").split(",")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(
            "Hallo! 👋 Ich bin leider nur für bestimmte Personen verfügbar."
        )
        return

    text = update.message.text
    await update.message.chat.send_action("typing")

    response = await brain.process(text, user_id)
    await update.message.reply_text(response)

async def handle_start(update: Update, context):
    await update.message.reply_text(
        "Hallo! Ich bin Lena, deine persönliche Assistentin 🌸\n\n"
        "Du kannst mir einfach schreiben was du brauchst, zum Beispiel:\n"
        "• 'Erinner mich morgen früh ans Zahnarzttermin'\n"
        "• 'Füg Milch und Brot zur Einkaufsliste hinzu'\n"
        "• 'Was hab ich diese Woche vor?'\n\n"
        "Ich bin immer da! 💬"
    )

def main():
    from telegram.ext import CommandHandler
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🌸 Lena ist online")
    app.run_polling()

if __name__ == "__main__":
    main()
```

---

## Schritt 5 – actions/reminders.py

```python
from supabase import create_client
import os
from datetime import datetime

db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

async def add_reminder(user_id: str, text: str, when: str) -> str:
    try:
        remind_at = datetime.fromisoformat(when)
        db.table("reminders").insert({
            "user_id": user_id,
            "text": text,
            "remind_at": remind_at.isoformat()
        }).execute()
        formatted = remind_at.strftime("%d.%m. um %H:%M Uhr")
        return f"⏰ Ich erinnere dich am {formatted}: {text}"
    except Exception as e:
        return f"❌ Konnte Erinnerung nicht setzen: {e}"

async def check_and_send_reminders(bot):
    """Läuft jede Minute – sendet fällige Erinnerungen"""
    now = datetime.now().isoformat()
    due = db.table("reminders") \
        .select("*") \
        .eq("sent", False) \
        .lte("remind_at", now) \
        .execute()

    for r in due.data:
        await bot.send_message(chat_id=r["user_id"],
            text=f"🔔 Erinnerung: {r['text']}")
        db.table("reminders").update({"sent": True}).eq("id", r["id"]).execute()
```

---

## Schritt 6 – actions/shopping.py

```python
from supabase import create_client
import os

db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

async def add_items(user_id: str, items: list) -> str:
    rows = [{"user_id": user_id, "item": i} for i in items]
    db.table("shopping_lists").insert(rows).execute()
    listed = "\n".join(f"• {i}" for i in items)
    return f"✅ Hinzugefügt:\n{listed}"

async def get_list(user_id: str) -> str:
    result = db.table("shopping_lists") \
        .select("item") \
        .eq("user_id", user_id) \
        .eq("done", False) \
        .execute()
    if not result.data:
        return "🛒 Deine Einkaufsliste ist leer!"
    items = "\n".join(f"• {r['item']}" for r in result.data)
    return f"🛒 Deine Einkaufsliste:\n{items}"

async def mark_done(user_id: str, item: str) -> str:
    db.table("shopping_lists") \
        .update({"done": True}) \
        .eq("user_id", user_id) \
        .ilike("item", f"%{item}%") \
        .execute()
    return f"✅ '{item}' abgehakt!"
```

---

## Schritt 7 – .env Vorlage

```bash
# Telegram
TELEGRAM_TOKEN=
ALLOWED_USER_IDS=telegram_id_1,telegram_id_2

# Anthropic
ANTHROPIC_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_KEY=
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

---

## Setup-Anleitung für neue Nutzerin (nicht-technisch)

```
1. Thomas richtet alles ein (einmalig, ~30 Minuten)
2. Nutzerin sucht auf Telegram nach dem Bot-Namen
3. Tippt /start
4. Lena erklärt sich selbst
5. Nutzerin schreibt einfach was sie braucht
→ Fertig.
```

---

## Implementierungs-Reihenfolge

```
1. Projektstruktur anlegen
2. Supabase Tabellen erstellen
3. memory.py implementieren
4. brain.py implementieren
5. main.py – Bot starten
6. actions/reminders.py
7. actions/shopping.py
8. actions/calendar.py
9. Watcher für Erinnerungen (jede Minute checken)
10. Railway Deployment
11. /start Command testen
12. Mit echter Nutzerin 1 Woche testen
```

---

## Anpassbarkeit (für verschiedene Nutzerinnen)

Das System ist so gebaut dass es für jede Person in 15 Minuten eingerichtet werden kann:

```
1. CLAUDE.md anpassen (Name, Kontext, Vorlieben)
2. .env mit neuen Telegram-IDs befüllen
3. Neue Railway-Instanz deployen
→ Fertig. Jede Person hat ihre eigene, private Assistentin.
```

---

## Definition of Done

- [ ] Bot antwortet auf /start mit freundlicher Begrüßung
- [ ] Erinnerungen werden korrekt gesetzt und gesendet
- [ ] Einkaufsliste funktioniert (hinzufügen, zeigen, abhaken)
- [ ] Kalendereinträge werden erstellt
- [ ] Gedächtnis bleibt nach Neustart erhalten
- [ ] Nur erlaubte Nutzerinnen haben Zugriff
- [ ] Läuft stabil auf Railway
- [ ] Nicht-technische Nutzerin versteht sofort wie es funktioniert
