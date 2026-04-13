# Multi-Channel ACA — Design Spec

**Datum:** 2026-04-13
**Autor:** Thomas Gaeta + Claude

---

## Überblick

Jeder YouTube/Instagram-Channel bekommt eine eigene ACA-Instanz (Autonomous Channel Agent) die als absoluter Nischen-Spezialist den Channel autonom bespielt. Der CYO (Chief YouTube Officer) erstellt, überwacht und koordiniert alle ACAs. Thomas kommuniziert ausschließlich über Susi.

## Hierarchie

```
CEO (Wochenstrategie)
  └── CYO (überwacht alle Channels)
        ├── ACA "Aurrraaaaaa" (stoicism, EN, Mo/Mi)
        │     ├── Thumbnail Artist
        │     ├── SEO Agent
        │     └── Performance Analyst
        ├── ACA "Channel 2" (true_crime, DE, Di/Do)
        │     ├── Thumbnail Artist
        │     ├── SEO Agent
        │     └── Performance Analyst
        └── ACA "Channel 3" (finance, IT, Fr)
              ├── Thumbnail Artist
              ├── SEO Agent
              └── Performance Analyst
```

## Channel-Config

Eine JSON-Datei pro Channel in `~/Documents/BotProjects/meta_memory/aca_channels/`:

```json
{
  "channel_id": "UC...",
  "handle": "Aurrraaaaaa",
  "niche": "stoicism",
  "language": "en",
  "production_days": ["monday", "wednesday"],
  "videos_per_week": 3,
  "reference_channels": ["UCxyz", "UCabc"],
  "style": "dark narration, cinematic",
  "status": "production",
  "youtube_oauth_token": "youtube_token.json",
  "created_at": "2026-04-13"
}
```

**Status-Werte:** `analyse` → `aufbau` → `produktion` → `live` → `paused`

## Shared vs. Channel-spezifisch

**Alle ACAs teilen (selber Code):**
- Brain-Logik (brain.py)
- Agent-Tools (Thumbnail Artist, SEO Agent, Performance Analyst)
- Sensing-Datenbank (Signale nach Nische gefiltert)
- YouTube Auth (wenn alle Channels unter demselben Google-Account)

**Jeder ACA hat eigenes:**
- Channel-Config (Nische, Sprache, Stil, Produktionstage)
- Performance-Tracking (nur seine Videos)
- Feedback-Loop (nur seine Nische gewichten)
- Produktions-Schedule (seine zugewiesenen Tage)

## Zwei-Ebenen Learnings

### Globale Learnings (CYO verteilt an alle ACAs)
- Thumbnail-Regeln: welche Farben, Schriftgrößen, Positionen die beste CTR bringen
- Hook-Formate: welche Patterns plattformübergreifend funktionieren
- Upload-Zeiten: wann die meisten Views kommen
- Allgemeine YouTube-Algorithmus-Erkenntnisse

### Channel-Learnings (nur eigener ACA)
- Welche Topics in seiner Nische performen
- Welche Konkurrenten am erfolgreichsten sind
- Nischenspezifischer Stil und Ton
- Eigene Performance-Historie als Gewichtung für Themenplanung

**Mechanismus:** CYO liest wöchentlich die Performance-Daten aller ACAs, extrahiert übertragbare Muster, speichert sie als `global_learnings.json`. Jeder ACA liest diese Datei beim Themen-Ranking als zusätzlichen Boost.

## Channel-Lifecycle

### 1. Analyse (du → Susi → CYO)
- Du sagst Susi: "Neuer Channel für True Crime"
- Susi triggert CYO
- CYO analysiert: Konkurrenz in der Nische, Opportunity-Score, Sprach-Empfehlung, Marktlücken
- CYO schickt Ergebnis an Susi → Susi präsentiert dir

### 2. Bestätigung Aufbau (Gate 1)
- Du bestätigst: "Ja, starten"
- CYO erstellt ACA-Config mit Nische, Sprache, Referenz-Channels
- Status: `aufbau`

### 3. Aufbau (ACA Phase 0)
- ACA übernimmt sofort
- Generiert: 3 Channel-Name-Vorschläge, Logo, Banner, Kanal-Beschreibung
- Erstellt: erste 5 Video-Ideen basierend auf Nischen-Analyse
- Susi präsentiert alles → du wählst/bestätigst

### 4. Bestätigung Produktion (Gate 2)
- Du bestätigst: "Produktion starten"
- CYO weist dem ACA Produktionstage zu (gestaffelt mit anderen Channels)
- Status: `produktion`

### 5. Laufender Betrieb (ACA autonom)
- Wöchentliche Themenplanung (Brain) → Susi fragt dich (Gate)
- Produktion an zugewiesenen Tagen (Tuby Pipeline)
- Fertiger Content → Susi zeigt Vorschau (Gate)
- Performance-Tracking täglich
- Feedback-Loop fließt in nächste Planung

### 6. CYO Überwachung
- Wöchentlicher Überblick über alle ACAs an CEO
- Alert wenn ein Channel 2 Wochen unter Durchschnitt
- Kann Strategie-Änderung vorschlagen ("Wechsel von Finance zu Investing-Nische")
- Verteilt globale Learnings

## Gestaffelte Produktion

Bei 3-5 Channels mit je 3 Videos/Woche:

| Tag | ACA |
|---|---|
| Montag | Channel 1 |
| Dienstag | Channel 2 |
| Mittwoch | Channel 1 |
| Donnerstag | Channel 3 |
| Freitag | Channel 2 |
| Samstag | Channel 3 |
| Sonntag | Planung (alle ACAs) |

CYO verteilt die Tage bei der ACA-Erstellung automatisch basierend auf freien Slots.

## YouTube OAuth

- Alle Channels unter demselben Google-Account: ein Token reicht
- Channels auf verschiedenen Accounts: ein Token pro Account
- Config-Feld `youtube_oauth_token` verweist auf die richtige Token-Datei

## Implementierungs-Scope

### Was gebaut werden muss:
1. **ACA Multi-Channel Runner** — brain.py wird channel-aware (liest Config, filtert nach Nische)
2. **Channel Registry** — `aca_channels/` Verzeichnis mit Config-Dateien, CRUD-Operationen
3. **CYO ACA-Management** — CYO kann neue ACAs erstellen, Configs generieren, Tage zuweisen
4. **Susi Channel-Actions** — "Neuer Channel" Aktion in Susi die den CYO triggert
5. **Gestaffelter Scheduler** — Scheduler liest Channel-Configs, triggert ACAs an ihren Tagen
6. **Globale Learnings** — CYO aggregiert, speichert, ACAs lesen

### Was NICHT in Scope:
- Instagram-Pipeline (eigenes Projekt)
- YouTube Auto-Upload (Phase 3, separat)
- Multi-Account OAuth (erst wenn nötig)
- Channel löschen/archivieren (manuell erstmal)
