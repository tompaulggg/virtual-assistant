# Autonomous Channel Agent (ACA) — Design Spec

**Datum:** 2026-04-12
**Autor:** Thomas Gaeta + Claude

---

## Überblick

Der ACA ist ein eigenständiger Python-Service der YouTube-Kanäle und Instagram-Accounts autonom bespielt. Er orchestriert Datensammlung, Themen-Planung, Content-Produktion und Publishing. Thomas kommuniziert ausschließlich über Susi — alle Agenten reporten an sie.

## Architektur

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   Sensing    │────▶│  ACA Brain   │────▶│  Production   │
│  (Daten)     │     │ (Orchestr.)  │     │  (Tuby + IG)  │
└─────────────┘     └──────┬───────┘     └───────────────┘
                           │
                    ┌──────▼───────┐
                    │     Susi     │
                    │  (Interface) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Telegram   │
                    │  (Thomas)    │
                    └──────────────┘
```

**Vier Schichten:**

1. **Sensing Layer** — sammelt Daten aus YouTube, Google Trends, Reddit, News, eigenen Analytics
2. **ACA Brain** — Orchestrator, plant Themen, triggert Produktion, managed Feedback-Loop
3. **Production Layer** — Tuby (YouTube-Videos), Instagram-Pipeline (Carousels/Reels), Thumbnail-Agent, SEO-Agent
4. **Susi** — einziges Interface zu Thomas, formatiert Agenten-Output, stellt Gates

**Standort:** Eigener Service in `~/Documents/BotProjects/agents/aca/`

---

## Model-Tiers (Tokenomics)

Prinzip: günstigstes Model das die Aufgabe gut genug erledigt. Kein Opus.

| Aufgabe | Model | Kosten/1M tok |
|---|---|---|
| Sensing (Daten sammeln) | Kein LLM | $0 |
| Trend-Scoring/Ranking | Gemini Flash | ~$0 |
| Themen-Vorschläge (5/Woche) | Haiku | $1/$5 |
| Script-Writing (YouTube) | Sonnet | $3/$15 |
| Thumbnail-Agent | Sonnet | $3/$15 |
| SEO/Metadaten-Agent | Haiku + Daten | $1/$5 |
| Visual Direction | Gemini Flash | ~$0 |
| Instagram Captions | Haiku | $1/$5 |
| Susi-Kommunikation | Haiku (default), Sonnet (komplex) | $1-3 |
| Feedback-Analyse | Haiku | $1/$5 |
| Strategie-Entscheidungen | Sonnet | $3/$15 |

**Geschätzte Wochenkosten ACA-Brain: ~$1-2** (ohne Bild-/Video-Generierung)

---

## Sensing Layer

Kontinuierliche Datensammlung, kein LLM nötig. Schreibt normalisierte Signale:

```json
{"source": "google_trends", "niche": "stoicism", "topic": "marcus aurelius quotes", "score": 85, "ts": "..."}
```

| Quelle | Was | Frequenz | Methode | Kosten |
|---|---|---|---|---|
| YouTube Trending | Trending Videos in Nische | alle 6h | YouTube Data API | Quota |
| Google Trends | Steigende Suchbegriffe | täglich | pytrends | $0 |
| Reddit | Hot Posts in Nischen-Subreddits | alle 4h | Reddit API | $0 |
| News | Breaking Topics zur Nische | alle 4h | NewsAPI | $0 (100 req/Tag) |
| Eigene DB | Top-Videos der 16k+ Channels | vorhanden | SQLite Query | $0 |
| YouTube Analytics | CTR, Retention eigener Videos | täglich | Analytics API | $0 |
| Instagram Insights | Reach, Saves, Shares | täglich | Graph API | $0 |

**Nicht in v1:** Twitter/X ($100/Monat, wenig Mehrwert für faceless Content)

---

## ACA Brain — Wöchentlicher Zyklus

### Sonntag 20:00 — Themen-Planung

1. Liest alle Signale der letzten 7 Tage
2. Rankt Themen per Gemini Flash: `Trend-Score × Nischen-Opportunity × Konkurrenz-Lücke × eigene Performance`
3. Generiert 5 YouTube-Themen + 7 Instagram-Posts (Haiku)
4. Meldet an Susi → Susi präsentiert Thomas den Wochenplan
5. **Gate 1:** Thomas wählt aus / ändert / genehmigt per Telegram

### Montag–Freitag — Produktion

- Pro YouTube-Thema: triggert Tuby-Pipeline per API (sequentiell)
- Pro Instagram-Post: triggert Instagram-Pipeline (wenn gebaut)
- Status-Updates an Susi ("Video 2/3 wird gerade produziert")

### Pro fertigem Content — Upload-Gate

- ACA meldet an Susi: "Content fertig"
- Susi schickt Thomas Vorschau + Titel + Thumbnail
- **Gate 2:** Thomas sagt Ja → ACA uploaded zum festen Zeitpunkt (v1: 17:00 CET)
- Thomas sagt Nein → ACA fragt was ändern

---

## Feedback-Loop (kontinuierlich)

### Täglich (automatisch, kein LLM)
- Alle eigenen Videos der letzten 90 Tage: Views, CTR, Avg. Retention, Likes, Kommentare
- Delta zum Vortag berechnen
- Instagram: Reach, Saves, Shares
- Erkennt "Sleeper"-Videos die plötzlich Traction bekommen

### Wöchentlich (Sonntag, Haiku)
- Performance-Zusammenfassung
- Welche Topics/Hooks haben funktioniert?
- Fließt direkt in Themen-Planung ein
- Beispiel: "Stoicism-Videos 3x besser als Finance → Gewichtung anpassen"

### Alert-basiert (sofort, an Susi)
- Video geht viral (ungewöhnlich viele Views in kurzer Zeit)
- Kommentar-Spike (könnte kontrovers sein)
- Unter-Performance wird leise notiert, kein Alert

---

## Thumbnail-Agent

Eigener spezialisierter Agent, weil Thumbnails den größten Einfluss auf CTR haben.

**Input:**
- Video-Titel und Script-Zusammenfassung
- Top-5 Thumbnails der Konkurrenz in der Nische (aus DB)
- Eigene bisherige Thumbnail-Performance (welcher Stil hat die beste CTR?)

**Prozess (Sonnet):**
1. Analysiert Konkurrenz-Thumbnails: Farben, Text-Placement, Emotionen, Kontrast
2. Generiert 3 Thumbnail-Konzepte mit detaillierten FLUX-Prompts
3. Fügt Text-Overlay hinzu (Pillow): max 4-5 Wörter, hoher Kontrast
4. Gibt alle 3 an Susi → Thomas wählt oder lässt den besten automatisch nehmen

**Model:** Sonnet für Konzept-Generierung, FLUX für Bildgenerierung, Pillow für Text-Overlay

---

## SEO/Metadaten-Agent

Generiert Titel, Description, Tags basierend auf Daten statt Bauchgefühl.

**Input:**
- Video-Script und Thema
- YouTube Search Suggest für das Thema (Autocomplete-Scraping)
- Titel der Top-10 Videos in der Nische (aus DB)
- Google Trends Suchvolumen für Keywords

**Output (Haiku):**
- 3 Titel-Varianten (A/B-Test-fähig, max 60 Zeichen)
- SEO-Description (500 Zeichen, Keywords vorne)
- 15-20 Tags (Mix aus High-Volume und Long-Tail)
- Hashtags für YouTube Shorts (falls relevant)

---

## Instagram-Pipeline (Carousel-fokussiert)

Eigenständige Pipeline, ähnlich Tuby aber für Instagram-Formate.

### Formate v1

**Carousels (5-10 Slides):**
- Infografik-Slides zu Nischen-Themen
- FLUX Bildgenerierung + Text-Overlay (Pillow)
- Konsistenter Brand-Stil (Farben, Fonts, Layout-Templates)
- Hook-Slide (Slide 1) + CTA-Slide (letzter Slide)

**Reels (15-90 Sek):**
- Kurzform-Content, eigenständig oder aus YouTube-Material abgeleitet
- Fal.ai Animation + ElevenLabs Voiceover + FFmpeg Assembly
- Vertikales 9:16 Format

### Pipeline-Schritte

1. **Topic Selection** — aus ACA Brain Wochenplan
2. **Content Writing** — Slide-Texte / Reel-Script (Haiku)
3. **Visual Design** — FLUX-Prompts generieren (Gemini Flash)
4. **Image Generation** — FLUX-Pro für Slides/Frames
5. **Text Overlay** — Pillow für Carousel, FFmpeg für Reels
6. **Caption + Hashtags** — Haiku generiert optimierte Captions
7. **Assembly** — Carousel-PDF/Bilder oder Reel-MP4

### Nischen-Vorschlag

Der ACA analysiert die Scout-DB und Instagram-spezifische Metriken um die beste Nische vorzuschlagen:
- Engagement-Rate > Views (Instagram-Metrik)
- Carousel-Tauglichkeit (Listicles, Fakten, Tipps = gut)
- Hashtag-Potenzial (Volumen + Konkurrenz)
- Cross-Platform-Lücke (auf YouTube stark, auf Instagram unterversorgt)

---

## Susi Smart-Routing (separates Mini-Projekt)

Susi nutzt aktuell immer Haiku. Erweiterung: automatische Model-Wahl pro Nachricht.

**Heuristik in Brain.py:**
- **Haiku (default):** Grüße, Status-Fragen, einfache Antworten, Zusammenfassungen, Ja/Nein-Fragen
- **Sonnet (upgrade):** Nachricht > 100 Zeichen mit Analyse-Keywords ("analysier", "vergleich", "strategie", "warum", "erkläre"), oder wenn Susi mehrere Agenten-Reports zusammenfassen muss

**Implementierung:** Kleiner Classifier vor dem API-Call — kann regelbasiert starten, später ML-basiert.

---

## OAuth2 Setup (einmalig, manuell)

Bevor der ACA uploaden kann, muss Thomas einmalig autorisieren:

**YouTube:**
1. Google Cloud Console → YouTube Data API v3 aktivieren
2. OAuth2 Credentials erstellen (Desktop App)
3. Einmal im Browser einloggen → Refresh Token speichern
4. ACA nutzt Refresh Token für alle Uploads

**Instagram:**
1. Meta Developer Portal → Instagram Graph API
2. Facebook Page mit Instagram Business Account verknüpfen
3. Long-lived Token generieren (60 Tage, auto-refresh)

---

## Datenbank-Schema (Erweiterung channels.db)

Neue Tabellen:

```sql
-- Sensing-Signale
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,          -- youtube_trends, google_trends, reddit, news
    niche TEXT NOT NULL,
    topic TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    raw_data TEXT DEFAULT '{}',    -- JSON mit Quelldaten
    created_at TEXT NOT NULL
);

-- Content-Plan
CREATE TABLE content_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week TEXT NOT NULL,            -- "2026-W16"
    platform TEXT NOT NULL,        -- youtube, instagram
    topic TEXT NOT NULL,
    format TEXT NOT NULL,          -- video, carousel, reel
    status TEXT DEFAULT 'proposed', -- proposed, approved, producing, ready, published, rejected
    tuby_job_id TEXT,              -- Link zur Tuby-Pipeline
    publish_at TEXT,
    performance TEXT DEFAULT '{}', -- JSON mit Analytics
    created_at TEXT NOT NULL
);

-- Feedback-Daten
CREATE TABLE performance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER REFERENCES content_plan(id),
    platform TEXT NOT NULL,
    date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    ctr REAL DEFAULT 0,
    avg_retention REAL DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0
);
```

---

## Scope & Reihenfolge

| Phase | Was | Abhängigkeit |
|---|---|---|
| 1 | Sensing Layer (Google Trends, Reddit, News, YouTube Trending) | - |
| 2 | ACA Brain + Susi-Integration (Wochenplan, Gates) | Phase 1 |
| 3 | YouTube Auto-Upload (OAuth2 + Data API v3) | - |
| 4 | Thumbnail-Agent | - |
| 5 | SEO/Metadaten-Agent | - |
| 6 | Feedback-Loop (YouTube Analytics) | Phase 3 |
| 7 | Instagram-Pipeline (Carousels + Reels) | Eigenes Projekt |
| 8 | Susi Smart-Routing | Eigenes Mini-Projekt |

Phase 1-6 = ACA v1 (YouTube autonom)
Phase 7 = ACA v2 (Instagram dazu)
Phase 8 = Susi-Upgrade (unabhängig)

---

## Nicht in Scope

- MiroFish Swarm-Simulation (kommt wenn echte Performance-Daten da sind)
- Twitter/X Scraping ($100/Monat, wenig Mehrwert in v1)
- TikTok / LinkedIn / andere Plattformen
- A/B Testing (Thumbnails, Titel) — v2 Feature
- Multi-Channel Management (ein Kanal pro Plattform in v1)
