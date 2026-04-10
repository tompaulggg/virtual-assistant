# Graph Report - /Users/admin/tuby  (2026-04-09)

## Corpus Check
- Large corpus: 850 files · ~11,697,394 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 999 nodes · 1636 edges · 84 communities detected
- Extraction: 58% EXTRACTED · 42% INFERRED · 0% AMBIGUOUS · INFERRED: 688 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `PipelineContext` - 76 edges
2. `Orchestrator` - 63 edges
3. `new_job()` - 35 edges
4. `job_done()` - 34 edges
5. `job_failed()` - 33 edges
6. `job_running()` - 30 edges
7. `saveState()` - 30 edges
8. `pollJob()` - 23 edges
9. `_get_conn()` - 23 edges
10. `PipelineContextV4` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Thomas Gaeta` --implements--> `Tuby (TubeClone)`  [EXTRACTED]
  Lebenslauf_Thomas_Gaeta_2026.pdf → requirements.txt
- `TubeClone Businessplan (AMS UGP)` --references--> `Tuby (TubeClone)`  [EXTRACTED]
  TubeClone_Businessplan_08.04.2026_final.pdf → requirements.txt
- `TubeClone Businessplan (AMS UGP)` --references--> `AMS Unternehmensgruendungsprogramm Wien`  [EXTRACTED]
  TubeClone_Businessplan_08.04.2026_final.pdf → tubeclone businessplan/KONTEXT.md
- `TubeClone Businessplan (AMS UGP)` --references--> `SaaS Credit-Based Pricing Model`  [EXTRACTED]
  TubeClone_Businessplan_08.04.2026_final.pdf → tubeclone businessplan/KONTEXT.md
- `TubeClone Businessplan (AMS UGP)` --references--> `Niche Arbitrage Strategy`  [EXTRACTED]
  TubeClone_Businessplan_08.04.2026_final.pdf → tubeclone businessplan/KONTEXT.md

## Hyperedges (group relationships)
- **V4 Pre-Production Pipeline** — visual_mapping, breakdown_service, moodboard_service, storyboard_service, image_prompt_agent, motion_prompt_agent [EXTRACTED 1.00]
- **Agent Pipeline Sequence** — analyst_agent, writer_agent, director_agent, animator_agent, orchestrator_agent, quality_gates [EXTRACTED 1.00]
- **Production Toolchain** — flux_image_gen, wan_kling_animation, elevenlabs_voiceover, gemini_client, claude_client [EXTRACTED 1.00]

## Communities

### Community 0 - "Frontend UI (app.js)"
Cohesion: 0.02
Nodes (145): addChannelUrlRow(), addVoiceDirection(), analyzeScoutChannel(), _appendSplitHandle(), applyFixesToAll(), _buildFixedPrompt(), buildModelRecommendation(), cfAddToTimeline() (+137 more)

### Community 1 - "API Request Models"
Cohesion: 0.04
Nodes (88): BaseModel, AnalystRequest, AnalyzeChannelRequest, AnalyzeMultiRequest, AnalyzeRequest, AnimateRequest, AnimatorRequest, api_save_channel() (+80 more)

### Community 2 - "API Endpoints (main.py)"
Cohesion: 0.05
Nodes (83): _analyst_task(), analyze(), _analyze_channel_task(), analyze_multi(), _analyze_multi_task(), _analyze_task(), animate_scenes(), _animate_task() (+75 more)

### Community 3 - "Pipeline Context & State"
Cohesion: 0.06
Nodes (40): PipelineContextV4, Store phase result (e.g., 'brief', 'treatment', etc.), Update phase_status dict, Append to orchestrator_log with timestamp, Write JSON to {base_dir}/{job_id}/szenen/szene_{nr:02d}/{filename}, Read JSON from {base_dir}/{job_id}/szenen/szene_{nr:02d}/{filename}, _get_job_helpers(), Tuby Pipeline v4 API endpoints. (+32 more)

### Community 4 - "Database Layer"
Cohesion: 0.07
Nodes (42): find_similar_channels_from_db(), get_channel_by_id(), get_channel_count(), _get_conn(), get_db_stats(), get_niche_scores(), get_saved_channels(), get_scout_queue() (+34 more)

### Community 5 - "Channel Research & Analysis"
Cohesion: 0.08
Nodes (41): analyze_channel(), _cache_get(), _cache_key(), _cache_set(), discover_channels(), discover_from_db(), _estimate_rpm(), _extract_niches() (+33 more)

### Community 6 - "Video Assembly (FFmpeg)"
Cohesion: 0.14
Nodes (24): assemble_video(), assemble_video_v4(), _concat_clips(), _duration(), _has_hevc(), _ken_burns_from_image(), loop_clip(), loop_reverse_clip() (+16 more)

### Community 7 - "Niche Crawler"
Cohesion: 0.12
Nodes (19): crawl_all_niches(), crawl_niche(), _crawler_loop(), is_crawling(), _load_rotation(), pick_query_for_niche(), services/crawler.py — Background channel crawler  Uses yt-dlp for YouTube search, Crawl one niche: yt-dlp search → YouTube API stats → upsert to DB.     Returns ( (+11 more)

### Community 8 - "Image Generation (FLUX)"
Cohesion: 0.16
Nodes (19): _build_prompt(), _extract_url(), _generate_consistent_character(), _generate_fal(), _generate_flux_redux(), _generate_huggingface(), generate_image(), _generate_pollinations() (+11 more)

### Community 9 - "Scout Tests"
Cohesion: 0.14
Nodes (17): _init_temp_db(), _make_temp_db(), Create a temp DB with schema applied, return (path, conn)., qualify_with_ai() returns list with all required keys per candidate., qualify_with_ai recommends 'it' when niche is saturated., run_scout() returns [] immediately when no candidates pass metric filter., run_scout() saves opportunities with score >= 6.0 and sends alerts., save_scout_opportunity + get_scout_queue round-trips correctly. (+9 more)

### Community 10 - "Legacy Agent System"
Cohesion: 0.17
Nodes (15): agent_analyse(), agent_bild_prompts(), agent_call(), agent_produktion(), agent_qualitaet(), agent_recherche(), agent_skript(), agent_vertonung() (+7 more)

### Community 11 - "Animation (Wan/Kling)"
Cohesion: 0.24
Nodes (16): _build_motion_prompt(), _download_replicate_output(), generate_clip(), generate_kling_clip(), _ken_burns(), _ltxv_i2v(), _luma_i2v(), Build a motion-focused prompt for Wan I2V from scene description. (+8 more)

### Community 12 - "YouTube Analysis"
Cohesion: 0.16
Nodes (13): analyze_video(), extract_style_fingerprint(), _extract_video_id(), _fetch_transcript(), merge_style_fingerprints(), _parse_iso_duration(), Synthesize one unified style fingerprint from multiple video analyses., Convert ISO 8601 duration (PT1H2M3S) to total seconds. (+5 more)

### Community 13 - "Writer V4 (4-Step)"
Cohesion: 0.24
Nodes (13): _call_sonnet(), _count_words(), generate_critique(), generate_draft(), generate_revision(), generate_treatment(), Count total words across all scenes., Step 3: Self-critique. Checks word count, pacing, quality. Uses Claude Sonnet. (+5 more)

### Community 14 - "Scout Agent"
Cohesion: 0.24
Nodes (11): _auto_save_to_mission_control(), _get_client(), qualify_with_ai(), Send a Telegram alert for a scout opportunity via Bot API., Full scout run: filter → qualify → save → alert → mark alerted.     Returns list, Save channel and notify Mission Control so it shows up in the Kanban., Metric filter: return channels meeting all Scout criteria.     Criteria: outlier, Gemini Flash batch analysis of candidates.     Returns candidates list with AI a (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.21
Nodes (11): build_character_face_prompt(), build_character_prompt(), build_location_prompt(), generate_character_refs(), generate_location_refs(), Generate reference images for recurring characters and locations., Build a FLUX prompt for a character face closeup., Build a FLUX prompt for an empty location reference. (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.23
Nodes (10): call_claude(), call_claude_json(), get_client(), Call Claude and return the text response., Call Claude and parse JSON from the response., call_gemini_flash(), call_gemini_pro(), _get_client() (+2 more)

### Community 17 - "Community 17"
Cohesion: 0.25
Nodes (10): animate_scenes(), assemble_final(), build_voiceover(), _fallback_chain(), Concat per-scene audio files into one voiceover track + extract scene_durations., Build fallback chain: primary → wan_i2v → ken_burns., Assemble final video using existing Tuby assembler., Run full V4 production: voiceover concat → animate → assemble.      This is the (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.27
Nodes (10): _build_qa_prompt(), check_clip(), check_clips(), extract_frame(), _get_client(), _get_temp_frame_path(), QA-check a batch of animated clips.      clips: [{scene_id, clip_path}]     scen, Return a deterministic temp path for the extracted frame. (+2 more)

### Community 19 - "Community 19"
Cohesion: 0.29
Nodes (10): _base_url(), _client(), generate_clip(), generate_image(), _poll(), Luma AI integration — image generation (Photon) + video/animation (Ray).  Requir, Animate an image using Luma Ray I2V. Returns output_path., Public base URL for serving local files to Luma (required for I2V). (+2 more)

### Community 20 - "Community 20"
Cohesion: 0.2
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 0.2
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 0.31
Nodes (9): _gemini_call_with_retry(), generate_script(), _get_client(), _plan_story_arc(), Pass 2: Write scenes following the story arc as a hard blueprint., Call Gemini with retry + model fallback. Tries flash → pro → flash., Two-pass script generation: arc planning (Pass 1) -> scene writing (Pass 2)., Pass 1: Plan the story arc from the WinningFormula. (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.31
Nodes (9): add_voice_direction(), generate_cast(), generate_script(), _get_client(), Use Gemini Flash to define a fixed visual cast for the video.     Returns dict w, Run all visual_prompt fields through Gemini to strip metaphors, thought bubbles,, Use Gemini to add ElevenLabs voice tags to narration for more expressive deliver, Generate a structured video script with scenes using Gemini. (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.28
Nodes (4): _make_test_png(), Write a minimal 1x1 white PNG for testing (used as fake extracted frame)., test_check_clip_passes(), test_check_clips_summary()

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (8): AMS Unternehmensgruendungsprogramm Wien, TubeClone Businessplan (AMS UGP), Language Strategy (EN to IT), Niche Arbitrage Strategy, SaaS Credit-Based Pricing Model, Scout Agent, Thomas Gaeta, Tuby (TubeClone)

### Community 26 - "Community 26"
Cohesion: 0.29
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.43
Nodes (5): _make_test_png(), Write a minimal 1x1 white PNG for testing., test_check_image_fails_high(), test_check_image_passes(), test_check_images_summary()

### Community 28 - "Community 28"
Cohesion: 0.29
Nodes (6): generate_voiceover(), get_audio_duration(), list_voices(), Return available ElevenLabs voices., Generate voiceover audio and save to output_path. Returns the path., Get duration of an audio file in seconds using moviepy.

### Community 29 - "Community 29"
Cohesion: 0.43
Nodes (6): _build_character_block(), generate_image_prompt(), generate_multi_image_prompts(), Build character description block from breakdown data., Build a FLUX image prompt for one scene., Generate multiple image prompts for one scene, each showing a different moment.

### Community 30 - "Community 30"
Cohesion: 0.43
Nodes (6): _build_qa_prompt(), check_image(), check_images(), _get_client(), QA-check a single generated image with Gemini Vision.      Returns {"scene_id":, QA-check a batch of images.      images: [{scene_id, image_path}]     scenes: [{

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (7): Unified 8-Step Pipeline Flow, ElevenLabs TTS Voiceover, FFmpeg Assembler, FLUX Image Generation (fal.ai), Pipeline Merge (V4 into Tuby), V4 Pipeline (Hollywood Pre-Production Model), Wan I2V + Kling 3.0 Animation

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (7): Analyst Agent, Animator Agent (Story-Arc-Aware), Director Agent, Orchestrator Agent (Dirigent), StoryArc (Writer Pass 1 Output), WinningFormula (Analyst Output), Writer Agent (Two-Pass / V4 4-Step)

### Community 33 - "Community 33"
Cohesion: 0.73
Nodes (5): _get_duration(), _make_test_clip(), test_loop_clip(), test_loop_reverse_clip(), test_slowmo_clip()

### Community 34 - "Community 34"
Cohesion: 0.53
Nodes (4): _mock_gemini_client(), test_plan_story_arc_beat_fields(), test_plan_story_arc_has_hook_and_climax(), test_plan_story_arc_has_scene_beats_per_scene()

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 0.4
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 0.4
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 0.4
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 0.4
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 0.7
Nodes (4): _mock_client(), test_analyze_winning_formula_required_keys(), test_analyze_winning_formula_three_act_blocks(), test_analyze_winning_formula_weaknesses_and_improvements_nonempty()

### Community 41 - "Community 41"
Cohesion: 0.5
Nodes (4): _call_haiku(), generate_scene_map(), Scene Mapper — assigns asset references to each scene., Map each scene to its asset references.

### Community 42 - "Community 42"
Cohesion: 0.6
Nodes (4): estimate_cost(), get_models(), get_scene_models(), Test/Production mode switch and model selection.

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (4): _extract_eye_constraint(), generate_cinematic_prompts(), Director Agent: enriches each scene's visual_prompt with cinematic direction., Extract eye color enforcement string from character_anchor.

### Community 44 - "Community 44"
Cohesion: 0.5
Nodes (2): Even if Gemini changes sprechtext, the original is restored., test_visual_mapping_preserves_sprechtext()

### Community 45 - "Community 45"
Cohesion: 0.5
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 0.5
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 0.5
Nodes (3): generate_edit_plan(), Editor agent — plans final video assembly., Plan the final video edit: timing, transitions, audio sync.

### Community 48 - "Community 48"
Cohesion: 0.5
Nodes (3): generate_breakdown(), Script Breakdown agent — extracts recurring characters and locations., Analyze script and extract recurring characters, locations, and one-off scenes.

### Community 49 - "Community 49"
Cohesion: 0.67
Nodes (3): analyze_winning_formula(), _get_client(), Analyze reference video data and extract a WinningFormula dict with 8 keys.

### Community 50 - "Community 50"
Cohesion: 0.5
Nodes (3): generate_visual_mapping(), Visual Mapping agent — maps narration text to visual descriptions., Take a narration-only script and add visueller_kern, charaktere, location per sc

### Community 51 - "Community 51"
Cohesion: 0.5
Nodes (3): generate_moodboard(), Moodboard agent — defines visual identity for the video., Define the visual identity — color palette, lighting, and style anchor.

### Community 52 - "Community 52"
Cohesion: 0.67
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 0.67
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (2): _make_ctx(), test_produce_scene()

### Community 55 - "Community 55"
Cohesion: 0.67
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 0.67
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 0.67
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 0.67
Nodes (0): 

### Community 59 - "Community 59"
Cohesion: 0.67
Nodes (2): Run a quality gate check for a pipeline step.      Returns {"pass": True} or {"p, run_quality_gate()

### Community 60 - "Community 60"
Cohesion: 0.67
Nodes (2): generate_motion_prompt(), Build a motion prompt for Kling or Wan based on the I2V model.

### Community 61 - "Community 61"
Cohesion: 0.67
Nodes (2): parse_gemini_json(), Parse JSON from a Gemini response robustly.      Handles:     - Markdown code fe

### Community 62 - "Community 62"
Cohesion: 0.67
Nodes (2): generate_motion_prompts(), Story-Arc-Aware Animator Agent.      Analyzes the full scene list as a narrative

### Community 63 - "Community 63"
Cohesion: 0.67
Nodes (2): check_image_quality(), QC check: does the generated image match the concept?     Returns {qc_score: 1-1

### Community 64 - "Community 64"
Cohesion: 0.67
Nodes (2): generate_storyboard(), Create per-scene storyboard with camera, composition, and clip strategies.

### Community 65 - "Community 65"
Cohesion: 0.67
Nodes (2): analyze_video_scenes(), Download video, upload to Gemini File API, and let Gemini natively analyse     s

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (0): 

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (0): 

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (0): 

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (0): 

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (0): 

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (0): 

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Image QA Agent

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Clip QA Agent

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Breakdown Service (Characters + Locations)

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Moodboard Service

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Storyboard Service

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Audio First Design Principle

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Clip Strategies (normal/slowmo/loop/reverse)

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Drei-Saeulen-Finanzierung

## Knowledge Gaps
- **191 isolated node(s):** `TubeClone — Die 7 KI-Agenten Jeder Agent hat einen klaren System-Prompt und gibt`, `Ruft einen Agenten auf und gibt das JSON-Ergebnis zurück.     agent_name: Nur fü`, `TubeClone — Orchestrator Koordiniert alle 7 Agenten und führt die komplette Pipe`, `Führt die komplette TubeClone Pipeline durch.      nische: z.B. "Finanzen & Inve`, `Startet einen einzelnen Agenten neu ohne die ganze Pipeline.      Beispiel:` (+186 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 66`** (2 nodes): `test_flux2pro.py`, `test_flux2pro_in_models()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (2 nodes): `test_breakdown.py`, `test_breakdown_extracts_recurring()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (2 nodes): `test_kling.py`, `test_kling_function_exists()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (2 nodes): `test_image_prompt_agent.py`, `test_generates_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (2 nodes): `test_editor_agent.py`, `test_edit_plan()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (2 nodes): `model_profiles.py`, `get_profile()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `vite.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `eslint.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `postcss.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Image QA Agent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Clip QA Agent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Breakdown Service (Characters + Locations)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Moodboard Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Storyboard Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Audio First Design Principle`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Clip Strategies (normal/slowmo/loop/reverse)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Drei-Saeulen-Finanzierung`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PipelineContext` connect `API Request Models` to `Pipeline Context & State`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 63 inferred relationships involving `PipelineContext` (e.g. with `AnalyzeRequest` and `ScriptRequest`) actually correct?**
  _`PipelineContext` has 63 INFERRED edges - model-reasoned connections that need verification._
- **Are the 58 inferred relationships involving `Orchestrator` (e.g. with `AnalyzeRequest` and `ScriptRequest`) actually correct?**
  _`Orchestrator` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `new_job()` (e.g. with `_run_scout_sync()` and `research_discover()`) actually correct?**
  _`new_job()` has 34 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `job_done()` (e.g. with `_discover_task()` and `_similar_task()`) actually correct?**
  _`job_done()` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `job_failed()` (e.g. with `_discover_task()` and `_similar_task()`) actually correct?**
  _`job_failed()` has 32 INFERRED edges - model-reasoned connections that need verification._
- **What connects `TubeClone — Die 7 KI-Agenten Jeder Agent hat einen klaren System-Prompt und gibt`, `Ruft einen Agenten auf und gibt das JSON-Ergebnis zurück.     agent_name: Nur fü`, `TubeClone — Orchestrator Koordiniert alle 7 Agenten und führt die komplette Pipe` to the rest of the system?**
  _191 weakly-connected nodes found - possible documentation gaps or missing edges._