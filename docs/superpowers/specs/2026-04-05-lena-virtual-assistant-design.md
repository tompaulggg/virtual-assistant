# Lena — Executive Assistant für Esther
## Design Spec

**Datum:** 2026-04-05
**Status:** Approved
**Pilot-User:** Esther (Thomas' Schwester, rechte Hand vom Vorstand)

---

## Kontext

Lena ist das erste Sub-Projekt der **Virtual Assistant Platform** — einer SaaS-Plattform die AI-Assistenten pro Berufsgruppe anbietet. Lena validiert den Shared Core und liefert gleichzeitig echten Nutzen für Esther.

### Plattform-Roadmap

1. **Lena** — Executive Assistant (Pilot: Esther) ← dieses Projekt
2. **Susi** — Gründer/Unternehmer (Pilot: Thomas)
3. **Arzt Core** — Zahnarztpraxen AT
4. **Arzt + Telefonie** — ElevenLabs/Twilio Layer
5. **Weitere Verticals** — Anwalt, Steuerberater, Makler, ...

### Architektur-Entscheidung

**Plugin-Architektur:** Shared Core der für alle Verticals gleich ist. Pro Vertical nur Config + Actions + Entry Point. Core kennt die Verticals nicht — er lädt was er bekommt.

---

## Projektstruktur

```
~/virtual-assistant/
├── core/
│   ├── __init__.py
│   ├── bot.py              ← Telegram Bot Basis (Message Handler, Auth, /start)
│   ├── brain.py            ← Claude API Client + Action Router
│   ├── memory.py           ← Supabase Client (Conversations, Facts)
│   ├── scheduler.py        ← APScheduler Wrapper (Reminders, Cron-Jobs)
│   └── types.py            ← Shared Dataclasses (Action, Config, etc.)
│
├── lena/
│   ├── main.py             ← Entry Point: importiert core/, registriert Actions
│   ├── config.yaml         ← Esther-Kontext, Persönlichkeit, Permissions
│   ├── actions/
│   │   ├── ghostwriter.py  ← Texte formulieren, Tonalität, Übersetzung
│   │   ├── todos.py        ← Tasks & Follow-ups
│   │   ├── briefing.py     ← Morgen-Briefing, Meeting-Vorbereitung
│   │   ├── knowledge.py    ← Wissensdatenbank (Firmen, Kontakte)
│   │   └── reminders.py    ← Erinnerungen
│   └── templates/          ← Vorlagen für wiederkehrende Texte
│
├── .env                    ← Secrets (nie committen)
├── requirements.txt
├── railway.toml
└── README.md
```

---

## Tech Stack

| Was | Tool | Begründung |
|-----|------|-----------|
| AI | `anthropic` — Claude Sonnet 4.5 | Effizient, günstig, reicht für Ghostwriting/Briefings |
| Interface | `python-telegram-bot` 20.x | Einfach, Esther kennt Telegram |
| Datenbank | `supabase` (Free Tier) | Kostenlos, reicht für Pilot |
| Scheduling | `apscheduler` 3.x | Cron-Jobs + Intervalle |
| Hosting | Railway | Einfach, günstig, 24/7 |

---

## Core Engine

### brain.py — Herzstück

```
User Message → Brain
  1. Lade Conversation History aus Memory
  2. Sende an Claude mit System-Prompt (aus config.yaml)
  3. Claude antwortet:
     - Text → direkt zurück an User
     - JSON Action → Router führt registrierte Action aus → Ergebnis zurück an User
  4. Speichere Conversation in Memory
```

Actions werden NICHT im Brain hardcoded. Der Vertical registriert sie beim Start:

```python
brain = Brain(config="lena/config.yaml")
brain.register_action("ghostwrite", ghostwriter.run)
brain.register_action("todo_add", todos.add)
brain.register_action("remind", reminders.set)
```

Claude bekommt die verfügbaren Actions automatisch im System-Prompt aufgelistet. Neuer Vertical = andere Actions registriert = anderer System-Prompt, gleicher Brain.

### memory.py

Abstrahierter DB-Client. Supabase für Lena/Susi, PostgreSQL für Arzt — Wechsel ist eine Config-Änderung.

### scheduler.py

Dünner Wrapper um APScheduler. Vertical registriert Cron-Jobs:
- Lena: Morgen-Briefing 7:30, Reminder-Check jede Minute
- Arzt (später): Terminerinnerungen 9:00, Rechnungsprüfung 11:00

---

## Config (lena/config.yaml)

```yaml
assistant:
  name: "Lena"
  language: "de"
  model: "claude-sonnet-4-5"
  max_tokens: 500

personality:
  style: "Freundlich und warm, wie eine gute Freundin"
  rules:
    - "Kurze, klare Antworten"
    - "Kein Technik-Jargon"
    - "Bei Unsicherheit nachfragen"
    - "Natürliche Sprache verstehen, keine Commands erzwingen"

user:
  name: "Esther"
  role: "Executive Assistant / Rechte Hand vom Vorstand"
  context: |
    Esther arbeitet als rechte Hand des Vorstands einer Firma.
    Sie schreibt täglich viele E-Mails und Nachrichten,
    koordiniert Termine, trackt Follow-ups und recherchiert.

permissions:
  allowed_without_asking:
    - reminders
    - todos
    - knowledge
    - ghostwrite
    - briefing
  requires_confirmation:
    - send_email
    - delete_data

scheduler:
  morning_briefing: "07:30"
  reminder_check_interval_seconds: 60
```

---

## Lena MVP Features

### 1. Ghostwriter (ghostwriter.py)
- Stichpunkte → professioneller Text
- Tonalität wählbar: formal, freundlich, kurz, englisch
- Übersetzung Deutsch ↔ Englisch
- Grammatik/Stil korrigieren
- **Beispiel:** "Schreib eine Absage an Müller, höflich aber bestimmt" → fertige E-Mail

### 2. To-Do & Follow-up Tracker (todos.py)
- Tasks anlegen mit optionaler Deadline und Priorität
- Offene Tasks auflisten
- Tasks abhaken
- Proaktive Erinnerung bei fälligen Deadlines
- **Beispiel:** "Freitag muss ich das Angebot an XY nachfassen"

### 3. Briefing (briefing.py)
- Automatisches Morgen-Briefing um 7:30: fällige Tasks, offene Follow-ups
- Meeting-Vorbereitung auf Anfrage: Kontext aus Wissensdatenbank + Recherche
- Abend-Zusammenfassung optional
- **Beispiel:** "Was steht morgen an?"

### 4. Wissensdatenbank (knowledge.py)
- Fakten merken: Firmen, Kontakte, Notizen
- Fuzzy-Suche: "der Typ von der Messe" → findet passenden Eintrag
- Kategorisiert: person, firma, notiz
- **Beispiel:** "Merke: Firma XY, Ansprechpartner Herr Schmidt, Tel 0664..."

### 5. Erinnerungen (reminders.py)
- Zeitgesteuerte Erinnerungen
- Wiederkehrend möglich ("jeden Montag")
- Scheduler prüft jede Minute auf fällige Reminders
- **Beispiel:** "Erinner mich morgen um 9 ans Telefonat"

### Bewusst NICHT im MVP
- Kalender-Integration (braucht OAuth)
- E-Mail-Integration (braucht Gmail API)
- Sprachnachrichten (braucht Whisper)
- Dokument-Zusammenfassung (kommt bei Susi)

---

## Datenbank-Schema

### Core-Tabellen (alle Verticals)

```sql
CREATE TABLE conversations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE facts (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    category text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE reminders (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    text text NOT NULL,
    remind_at timestamptz NOT NULL,
    recurring text,
    sent boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);
```

### Lena-spezifische Tabellen

```sql
CREATE TABLE todos (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    title text NOT NULL,
    status text DEFAULT 'open',
    due_date date,
    priority text DEFAULT 'normal',
    created_at timestamptz DEFAULT now()
);

CREATE TABLE knowledge (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    category text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE templates (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    name text NOT NULL,
    content text NOT NULL,
    created_at timestamptz DEFAULT now()
);

```

### Core-Tabelle: Audit Log (alle Verticals)

```sql
CREATE TABLE audit_log (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id text NOT NULL,
    action text NOT NULL,
    details jsonb,
    created_at timestamptz DEFAULT now()
);
```

---

## Sicherheit

### Auth
- Nur erlaubte Telegram User-IDs (aus `.env`) können mit dem Bot reden
- Unbekannte User bekommen höfliche Absage

### Audit Log
- Jede Action wird protokolliert (wer, was, wann)
- Leichtgewichtig als Supabase-Tabelle
- Basis für den Arzt-Vertical wo Audit Pflicht ist

### Rate Limiting
- Max 20 Nachrichten pro Minute pro User (verhindert Spam/Missbrauch)

### Input Sanitization
- User-Nachrichten werden bereinigt bevor sie an Claude gehen
- Prompt Injection Prevention: System-Prompt ist geschützt

### Secrets
- Alle Credentials nur in `.env`
- `.env` in `.gitignore`
- Nie in Config, Code, oder Logs

---

## Error Handling

- **Claude API down:** "Ich hab gerade ein technisches Problem, versuch's in ein paar Minuten nochmal"
- **Supabase down:** Nachricht trotzdem beantworten (ohne History), Fehler loggen
- **Action fehlgeschlagen:** Klare Fehlermeldung an User, kein Stacktrace
- **Logging:** stdout (Railway Console zeigt es)

---

## Deployment

- **Lokal entwickeln** — alles testen ohne Server
- **Railway deployen** — `python lena/main.py`
- **Pro Vertical eigene Railway-Instanz** — isoliert, eigene DB, eigener Bot

```toml
# railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python lena/main.py"
restartPolicyType = "always"
```

---

## .env Vorlage

```bash
# Telegram
TELEGRAM_TOKEN=
ALLOWED_USER_IDS=

# Anthropic
ANTHROPIC_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_KEY=
```

---

## Definition of Done (Lena MVP)

- [ ] Bot antwortet auf /start mit freundlicher Begrüßung
- [ ] Ghostwriter: Stichpunkte → professioneller Text
- [ ] Todos: anlegen, auflisten, abhaken, Deadline-Erinnerung
- [ ] Morgen-Briefing kommt automatisch um 7:30
- [ ] Wissensdatenbank: merken und abrufen
- [ ] Erinnerungen werden korrekt gesetzt und gesendet
- [ ] Natürliche Sprache — keine Commands nötig
- [ ] Nur Esther hat Zugriff (Telegram ID Auth)
- [ ] Audit Log aktiv
- [ ] Gedächtnis bleibt nach Neustart erhalten
- [ ] Läuft stabil auf Railway
- [ ] Esther versteht sofort wie es funktioniert
