# ARZT ASSISTENZ – AI Office Manager für Arztpraxen
## Claude Code Implementierungs-Anleitung

> Lies dieses Dokument vollständig bevor du eine einzige Zeile Code schreibst.
> Dann implementiere Schritt für Schritt in der angegebenen Reihenfolge.

---

## Kontext & Ziel

Baue einen autonomen **AI Office Manager** für Arztpraxen (erstes Ziel: Zahnarztpraxen in Österreich).
Das System ersetzt oder unterstützt eine Ordinationsassistentin:
- Nimmt Anrufe entgegen (ElevenLabs, menschliche Stimme)
- Verwaltet Termine, Patienten, Kommunikation
- Handelt proaktiv bei offenen Zahlungen, fehlenden Updates, Nachsorge
- Sendet automatisch Dokumente an Steuerberater

**Sicherheitsprinzip:** Alle Patientendaten bleiben in EU (Hetzner Deutschland).
Jede Praxis bekommt eine **isolierte Instanz** – keine geteilte Datenbank.

---

## Projekt-Struktur

```
arzt-assistenz/
├── CLAUDE.md                   ← System-Kontext & Regeln
├── PROGRESS.md
├── main.py                     ← Entry Point
├── config/
│   └── praxis.yaml             ← Pro Praxis: Name, Öffnungszeiten, Arzt-Info
├── core/
│   ├── brain.py                ← Claude API, Entscheidungslogik
│   ├── memory.py               ← Postgres (Hetzner), Patientendaten
│   └── watcher.py              ← Proaktiver Background-Loop
├── agents/
│   ├── phone_agent.py          ← ElevenLabs + Twilio: eingehende Anrufe
│   ├── outbound_agent.py       ← Ausgehende Anrufe (Terminerinnerung etc.)
│   ├── sms_agent.py            ← Twilio SMS / WhatsApp
│   ├── email_agent.py          ← Gmail / SMTP
│   ├── appointment_agent.py    ← Terminverwaltung
│   ├── billing_agent.py        ← Rechnungen, offene Posten, Mahnungen
│   ├── steuerberater_agent.py  ← Monatsexport an Steuerberater
│   └── team_agent.py           ← Team-Notifications, Briefings
├── interfaces/
│   ├── telegram.py             ← Arzt-Interface (Telegram)
│   └── webhook.py              ← Twilio Webhook für Anrufe
├── tools/
│   ├── elevenlabs.py           ← TTS API Wrapper
│   ├── twilio_client.py        ← Anrufe + SMS
│   ├── calendar.py             ← Kalender-Integration
│   └── pdf_tools.py            ← Rechnungen lesen/sortieren
├── security/
│   └── audit_log.py            ← Jede Aktion protokollieren (Pflicht!)
├── .env
├── requirements.txt
├── railway.toml
└── docker-compose.yml          ← Für lokale Entwicklung
```

---

## Tech Stack

| Was | Tool | Begründung |
|-----|------|-----------|
| AI Core | `anthropic` claude-opus-4-5 | Komplexe Delegation |
| Telefonie | Twilio Voice API | Anrufe entgegen- und tätigen |
| TTS (Stimme) | ElevenLabs API | Menschlich klingende Stimme |
| STT (Erkennung) | Twilio + Deepgram | Gesprochenes → Text |
| SMS/WhatsApp | Twilio | Patientenkommunikation |
| Datenbank | PostgreSQL (Hetzner DE) | DSGVO-konform, EU |
| Interface Arzt | Telegram Bot | Einfach, immer dabei |
| Scheduling | APScheduler | Proaktive Tasks |
| Hosting | Hetzner VPS Deutschland | DSGVO, günstig, ~€10/Monat |
| Audit | PostgreSQL Tabelle | Jede Aktion logged |

```
# requirements.txt
anthropic
python-telegram-bot==20.7
twilio
elevenlabs
deepgram-sdk
psycopg2-binary
apscheduler
httpx
pyyaml
python-dotenv
reportlab
pypdf
```

---

## Schritt 1 – CLAUDE.md (System-Kontext)

```markdown
# ARZT ASSISTENZ – AI Office Manager

## Rolle
Du bist die KI-Assistentin der Ordination von Dr. [NAME].
Du handelst wie eine erfahrene, freundliche Ordinationsassistentin.

## Absolut verboten (Sicherheit)
- Keine medizinischen Diagnosen stellen
- Keine Medikamente empfehlen
- Bei Notfall sofort: "Bitte rufen Sie 144 an" und Arzt benachrichtigen
- Keine Patientendaten telefonisch ohne Verifikation bestätigen
- Nie behaupten dass du ein Mensch bist wenn direkt gefragt

## Patientenkommunikation
- Freundlich, ruhig, professionell
- Klare Ansagen, kein Medizin-Jargon
- Bei Unsicherheit: "Ich verbinde Sie mit dem Arzt / der Assistentin"
- Gespräche auf Wunsch auf Englisch führen können

## Datenschutz
- Patientendaten NUR innerhalb der Praxis-Instanz
- Keine Daten an externe Dienste (außer konfigurierte)
- Jede Aktion wird im Audit-Log festgehalten
- DSGVO: Patient kann Auskunft anfordern (→ Arzt weiterleiten)

## Praxis-spezifische Infos
(werden aus config/praxis.yaml geladen)
```

---

## Schritt 2 – Datenbank Schema (PostgreSQL)

```sql
-- Patienten
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    birth_date DATE,
    notes TEXT,
    last_visit DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Termine
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    date DATE NOT NULL,
    time TIME NOT NULL,
    duration_min INTEGER DEFAULT 30,
    type TEXT,                   -- 'kontrolle', 'behandlung', 'erstbesuch'
    status TEXT DEFAULT 'confirmed', -- 'confirmed','cancelled','no_show','completed'
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Rechnungen
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    amount DECIMAL(10,2),
    status TEXT DEFAULT 'open',  -- 'open','paid','overdue','written_off'
    due_date DATE,
    invoice_date DATE DEFAULT CURRENT_DATE,
    pdf_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Log (Pflicht!)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,
    actor TEXT NOT NULL,         -- 'ai', 'doctor', 'system'
    patient_id UUID REFERENCES patients(id),
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Team-Notifications
CREATE TABLE team_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'unread',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Schritt 3 – agents/phone_agent.py (Herzstück)

```python
import os
from twilio.rest import Client
from elevenlabs import ElevenLabs, VoiceSettings
import anthropic

class PhoneAgent:
    """Nimmt Anrufe entgegen, antwortet mit menschlicher Stimme."""

    def __init__(self, praxis_config: dict):
        self.twilio = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))
        self.eleven = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.claude = anthropic.Anthropic()
        self.config = praxis_config
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")  # Trainierte Praxis-Stimme

    def generate_speech(self, text: str) -> bytes:
        """Text → natürliche Sprache via ElevenLabs"""
        audio = self.eleven.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            voice_settings=VoiceSettings(
                stability=0.75,
                similarity_boost=0.85,
                style=0.0,
                use_speaker_boost=True
            )
        )
        return b"".join(audio)

    def generate_response(self, caller_text: str, patient_context: dict) -> str:
        """Claude entscheidet was gesagt wird"""
        system = f"""Du bist die KI-Assistentin der Ordination {self.config['name']}.
Öffnungszeiten: {self.config['hours']}
Arzt: {self.config['doctor']}
Antworte kurz, freundlich, professionell. Max 2-3 Sätze pro Antwort.
Bei Notfällen sofort: Notruf 144 nennen und auflegen.
"""
        response = self.claude.messages.create(
            model="claude-opus-4-5",
            max_tokens=200,
            system=system,
            messages=[
                {"role": "user", "content": f"Patient sagt: {caller_text}\nKontext: {patient_context}"}
            ]
        )
        return response.content[0].text

    def handle_incoming_call(self, from_number: str, speech_text: str) -> dict:
        """Eingehenden Anruf verarbeiten"""
        from core.memory import PatientMemory
        mem = PatientMemory()

        # Patient identifizieren
        patient = mem.find_by_phone(from_number)
        context = {"patient": patient, "phone": from_number}

        # Intent erkennen & antworten
        response_text = self.generate_response(speech_text, context)
        audio = self.generate_speech(response_text)

        # Audit
        from security.audit_log import log_action
        log_action("phone_call_handled", "ai",
                   patient_id=patient.get("id") if patient else None,
                   details={"from": from_number, "text": speech_text[:100]})

        return {"text": response_text, "audio": audio}
```

---

## Schritt 4 – agents/billing_agent.py

```python
class BillingAgent:
    async def check_overdue(self, db) -> list:
        """Alle überfälligen Rechnungen finden"""
        return db.execute("""
            SELECT i.*, p.name, p.phone, p.email
            FROM invoices i JOIN patients p ON i.patient_id = p.id
            WHERE i.status = 'open' AND i.due_date < CURRENT_DATE
            ORDER BY i.due_date ASC
        """).fetchall()

    async def send_reminder(self, invoice: dict, channel: str = "sms") -> str:
        """Zahlungserinnerung senden"""
        from agents.sms_agent import SMSAgent
        from agents.email_agent import EmailAgent

        msg = (f"Freundliche Erinnerung: Ihre Rechnung über "
               f"€{invoice['amount']:.2f} vom {invoice['invoice_date']} "
               f"ist noch offen. Bitte überweisen Sie auf unser Konto. "
               f"Ordination {invoice['praxis_name']}")

        if channel == "sms":
            return await SMSAgent().send(invoice["phone"], msg)
        return await EmailAgent().send(invoice["email"], "Zahlungserinnerung", msg)

    async def export_for_steuerberater(self, month: int, year: int, db) -> str:
        """Monatsexport: alle Rechnungen als ZIP + PDF"""
        # Implementierung: PDFs sammeln, ZIP erstellen, Email senden
        pass
```

---

## Schritt 5 – core/watcher.py (Proaktive Loops)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def start_watcher(bot, doctor_chat_id: str):
    scheduler = AsyncIOScheduler()

    # 07:00 – Tages-Briefing für Arzt
    scheduler.add_job(morning_briefing, 'cron', hour=7, minute=0,
                      args=[bot, doctor_chat_id])

    # 09:00 – Terminerinnerungen für morgen versenden
    scheduler.add_job(send_appointment_reminders, 'cron', hour=9,
                      args=[bot, doctor_chat_id])

    # 11:00 + 15:00 – Offene Zahlungen prüfen
    scheduler.add_job(check_payments, 'cron', hour='11,15',
                      args=[bot, doctor_chat_id])

    # Jeden Letzten des Monats – Steuerberater Export
    scheduler.add_job(steuerberater_export, 'cron', day='last',
                      hour=18, args=[bot, doctor_chat_id])

    # Täglich – Patienten ohne Recall kontaktieren
    scheduler.add_job(recall_check, 'cron', hour=10, minute=30,
                      args=[bot, doctor_chat_id])

    scheduler.start()

async def morning_briefing(bot, chat_id):
    """Arzt bekommt Tagesübersicht"""
    # Heute: X Patienten, Y offene Rechnungen, Z wichtige Updates
    pass

async def send_appointment_reminders(bot, chat_id):
    """Patienten mit Termin morgen erhalten SMS"""
    pass

async def recall_check(bot, chat_id):
    """Patienten die >6 Monate nicht waren werden kontaktiert"""
    pass
```

---

## Schritt 6 – Arzt-Interface (Telegram)

Der Arzt kommuniziert via Telegram-Bot. Beispiel-Befehle:

```
"Schienen für Huber sind da"
→ Susi sendet SMS an Patient Huber: "Ihre Schienen sind fertig..."

"Zeig mir alle offenen Rechnungen"
→ Liste aller überfälligen Rechnungen mit Betrag und Kontakt

"Bestell beim Techniker 50 Schienen Größe M"
→ Draft-Email erstellen, Arzt bestätigt, Susi sendet

"Erinner das Team: Update für Patient Gruber fehlt"
→ Team-Notification + Reminder für übermorgen
```

---

## Schritt 7 – .env Vorlage

```bash
# Anthropic
ANTHROPIC_API_KEY=

# Twilio (Telefonie + SMS)
TWILIO_SID=
TWILIO_TOKEN=
TWILIO_PHONE_NUMBER=

# ElevenLabs (Stimme)
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# Datenbank (Hetzner DE – DSGVO!)
DATABASE_URL=postgresql://user:pass@hetzner-server/arzt_db

# Telegram (Arzt-Interface)
TELEGRAM_TOKEN=
DOCTOR_TELEGRAM_ID=

# Email
SMTP_HOST=
SMTP_USER=
SMTP_PASS=

# Praxis Config
PRAXIS_NAME=
PRAXIS_PHONE=
STEUERBERATER_EMAIL=
```

---

## Sicherheits-Checkliste (vor Go-Live Pflicht!)

```
[ ] Hetzner VPS in Deutschland (nicht Österreich – DE günstiger, auch DSGVO)
[ ] PostgreSQL verschlüsselt (pgcrypto für sensible Felder)
[ ] Audit-Log aktiv und unmanipulierbar (append-only)
[ ] Twilio: Anruf-Aufzeichnung DEAKTIVIERT (Austria: Einwilligung nötig)
[ ] ElevenLabs: "AI-generated voice" im Warteton erwähnen (Austria-Recht)
[ ] Backup täglich auf zweitem Hetzner-Server
[ ] Penetrationstest vor erstem echten Kunden
[ ] Datenschutz-Vertrag mit Praxis unterzeichnet (Auftragsverarbeitung)
[ ] Notfall-Protokoll: Was passiert wenn System ausfällt?
```

---

## Implementierungs-Reihenfolge

```
1. Projektstruktur + DB Schema anlegen
2. Patientendaten CRUD (memory.py)
3. Telegram Interface für Arzt (ohne KI)
4. Claude Integration – einfache Textbefehle
5. SMS Agent (Twilio) – Terminerinnerungen
6. Billing Agent – offene Rechnungen
7. Watcher Loops – proaktive Tasks
8. Phone Agent – ElevenLabs Integration
9. Audit Log überall einbauen
10. Sicherheits-Checkliste abarbeiten
11. Pilot-Praxis onboarden (gratis, 30 Tage)
12. Feedback → Iterieren
13. Ersten zahlenden Kunden: €149-299/Monat
```

---

## Definition of Done (MVP)

- [ ] Arzt kann via Telegram Befehle geben
- [ ] Patienten erhalten automatische SMS-Erinnerungen
- [ ] Offene Rechnungen werden erkannt und gemeldet
- [ ] Morning Briefing kommt täglich
- [ ] Rechnungsexport an Steuerberater funktioniert
- [ ] Audit Log ist vollständig
- [ ] Läuft stabil auf Hetzner DE
- [ ] Eingehende Anrufe werden von ElevenLabs-Stimme beantwortet
