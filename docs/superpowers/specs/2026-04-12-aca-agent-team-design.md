# ACA Agent Team — Design Spec

**Datum:** 2026-04-12
**Autor:** Thomas Gaeta + Claude

---

## Überblick

Drei spezialisierte Agents die dem ACA Brain zur Verfügung stehen. Jeder hat eine klare Aufgabe, eigene Schnittstelle und nutzt das günstigste passende Model.

## Architektur

```
ACA Brain (Orchestrator)
    │
    ├── calls ──▶ Thumbnail Artist
    │               ├── Input: Script, Nische, Konkurrenz-Thumbnails
    │               ├── Output: 3 Varianten (FLUX-Bild + Pillow Text-Overlay)
    │               └── Model: Gemini Flash + FLUX + Pillow
    │
    ├── calls ──▶ SEO Agent
    │               ├── Input: Script, Nische, Search Suggest, Konkurrenz-Titel
    │               ├── Output: 3 Titel, Description, Tags
    │               ├── Nachträglich: nach 7 Tagen bei schwacher Performance
    │               └── Model: Haiku + Daten
    │
    └── calls ──▶ Performance Analyst
                    ├── Input: YouTube API (alle Metriken)
                    ├── Speichert: alles in DB
                    ├── Analysiert: Views, CTR, Retention
                    ├── Alert: viral / underperformance
                    └── Model: kein LLM (Tracking), Haiku (Zusammenfassung)
```

**Standort:** `~/Documents/BotProjects/agents/aca/agents/`

---

## Model-Kosten

| Agent | Model | Kosten pro Aufruf |
|---|---|---|
| Thumbnail Artist | Gemini Flash (Konzept) + FLUX (~$0.05/Bild) + Pillow | ~$0.15 (3 Varianten) |
| SEO Agent | Haiku + Scraping | ~$0.01 |
| Performance Analyst | Kein LLM (Tracking), Haiku (Wochenbericht) | ~$0.01/Woche |

---

## Performance Analyst

### Modus 1 — Tägliches Tracking (sofort, ohne OAuth)

- Scrapt eigene Video-Metriken via yt-dlp: Views, Likes, Kommentare
- Speichert tägliche Snapshots in `performance_log` Tabelle
- Erkennt Trends: Video X hat heute 3x mehr Views als gestern
- Kein LLM, kein OAuth, kostenlos

### Modus 2 — Volle Analytics (braucht OAuth, später)

- YouTube Analytics API: CTR, Impressions, Avg. Retention, Traffic Sources, Watch Time, Subscriber-Gewinn, Revenue
- Alles wird gespeichert, auch wenn nicht alles sofort analysiert wird
- CYO und CEO können die vollen Daten für Reports nutzen

### Alerts an Susi

- Video geht viral: Views > 5x Durchschnitt in 24h
- 7-Tage-Check: Video underperformed (Views < 50% vom Kanal-Durchschnitt) → triggert SEO Agent

### Wöchentliche Zusammenfassung (Haiku)

- Top/Flop Videos der Woche
- Welche Nischen/Hooks/Formate am besten performen
- Fließt direkt in ACA Brain Themenplanung ein

### DB-Schema

```sql
-- Erweitert die bestehende performance_log Tabelle aus der ACA Spec
CREATE TABLE IF NOT EXISTS performance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'youtube',
    date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    -- OAuth-only Felder (NULL bis OAuth aktiviert)
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
);
CREATE INDEX IF NOT EXISTS idx_perf_video ON performance_log(video_id);
CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_log(date);
```

### Scheduling

- Tägliches Tracking: 06:00 UTC (vor dem Morning Briefing)
- Wöchentliche Zusammenfassung: Sonntag 19:00 (vor ACA Brain um 20:00)
- Alerts: bei jedem Tracking-Lauf, sofort an Susi

---

## SEO Agent

### Vor Upload (pro Video)

1. Scrapt YouTube Search Suggest (Autocomplete) für das Thema — kostenlos, kein API-Key
2. Holt Top-10 Titel der Konkurrenz aus der Tuby DB
3. Generiert per Haiku:
   - 3 Titel-Varianten (max 60 Zeichen, clickbait aber akkurat)
   - SEO-Description (500 Zeichen, Keywords vorne)
   - 15-20 Tags (Mix aus High-Volume und Long-Tail)

### Nachoptimierung (nach 7 Tagen)

1. Performance Analyst flaggt schwache Videos
2. SEO Agent holt aktuelle Search Suggest Daten (könnten sich geändert haben)
3. Generiert neuen Titel + Tags
4. Schickt an Susi → Thomas genehmigt
5. Wenn YouTube Upload (Phase 3) existiert: automatisch ändern

### Datenquellen

- YouTube Search Suggest: `https://suggestqueries.google.com/complete/search?client=youtube&q={query}` — kostenlos, kein Key
- Konkurrenz-Titel aus Tuby DB: `channels.top_videos_json`
- Performance-Daten vom Performance Analyst

---

## Thumbnail Artist

### Pro Video — 3 Varianten

1. Holt Top-5 Thumbnails der Konkurrenz in der Nische aus DB (`video_thumbs`)
2. Gemini Flash analysiert Konkurrenz: Farben, Komposition, Text-Stil, was funktioniert
3. Generiert 3 verschiedene FLUX-Prompts (verschiedene Konzepte/Stimmungen)
4. FLUX generiert die Bilder (1280x720, 16:9)
5. Pillow fügt Text-Overlay hinzu
6. Alle 3 an Susi → Thomas wählt oder sagt "nimm die Beste"

### Text-Overlay Regeln (Pillow)

- Max 5 Wörter
- Schriftgröße: mindestens 1/5 der Bildhöhe
- Immer Outline (3px schwarz) oder Drop-Shadow für Lesbarkeit
- Farbe: hoher Kontrast zum Hintergrund (weiß/gelb auf dunkel, schwarz auf hell)
- Position: oberes oder unteres Drittel, nie Mitte
- Font: Bold, Sans-Serif (Impact, Bebas Neue, oder ähnlich)

### Feedback-Loop

Der Thumbnail Artist lernt aus Performance-Daten:
- Performance Analyst speichert welcher Thumbnail-Stil (Farbe, Text-Position, Thema) welche CTR hat
- Thumbnail Artist liest die besten Stile als Kontext bevor er neue Varianten generiert
- Beispiel: "Rote Schrift auf dunklem Hintergrund → 8.2% CTR vs. weiße Schrift → 4.1% CTR"
- Benötigt: `thumbnail_meta` Feld in content_plan (speichert Stil-Tags pro Thumbnail)

---

## Implementierungs-Reihenfolge

| Schritt | Agent | Warum zuerst |
|---|---|---|
| 1 | Performance Analyst | Liefert Daten für alle anderen |
| 2 | SEO Agent | Braucht Performance-Daten für Nachoptimierung |
| 3 | Thumbnail Artist | Unabhängig, aber profitiert vom Feedback-Loop |

---

## Nicht in Scope

- YouTube Upload / automatische Titel-Änderung (Phase 3)
- Instagram-spezifische Agents (eigenes Projekt)
- A/B Testing (Thumbnails, Titel) — v2 Feature
- Multi-Kanal (erstmal ein Kanal)
