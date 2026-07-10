# DailyDex Project Handover Document for Claude

Welcome, Claude! This document provides a comprehensive, transparent, and actionable engineering handover for **DailyDex**—an autonomous AI creator platform designed to discover high-signal tech debates (Hacker News, Reddit) and automatically produce breakout 1080x1920 vertical video Shorts with data-backed technical evidence.

---

## 1. Executive Summary & Vision

- **Project Purpose**: DailyDex replaces generic AI content spam with data-grounded, empirically verifiable technical Shorts targeted at software engineers, DevOps specialists, and tech founders.
- **Core Value Proposition**: Instead of generic "AI tips", DailyDex discovers real-world engineering failures, runaway billing incidents, and local AI breakthroughs, presenting them with interactive CLI proof, metric gauges, professional voiceovers, and dynamic subtitles.
- **Current Status**:
  - **Signal Mining**: Operational (`src/creator_signal_miner.py`).
  - **Script & Hook Generation**: Operational (`src/clip_generator.py`).
  - **ElevenLabs Narration**: Operational (`src/video_renderer.py` using `Charlie` voiceover).
  - **Multi-Track Audio Mixing**: Operational (ElevenLabs voiceover mixed over a custom atmospheric lo-fi synth bed `src/data/bg_music.wav` at 18% volume).
  - **Interactive Web Cockpit**: Operational (`src/dashboard_new.py` running locally on port `8888`).

---

## 2. User Feedback & Critical Focus Area for Claude

### Where Previous Iterations Fell Short:
The user expressed strong dissatisfaction with programmatic 2D Python Pillow visual overlays and frame-manipulated still images for representing a human presenter (`avatar_talk_0..3.png` composited inside a webcam circle).

### What the User Wants Next:
1. **Broadcast-Quality Visuals & Real Video B-Roll / Avatars**:
   - Replace Python Pillow 2D animated avatar circles with true photorealistic AI video workflows (e.g., integrating dedicated AI video talking-head APIs such as **HeyGen API**, **Hedra API**, **D-ID**, or **ElevenLabs Creative Studio / Expressive Video workflows**).
   - Alternatively, compose real MP4 B-roll footage and motion graphics rather than static code-drawn canvases.
2. **Total Text Polish**: Ensure zero text collisions, zero string truncations, and pristine typographic hierarchy across all layouts.
3. **End-to-End Production Value**: Ensure the resulting videos look indistinguishable from top-tier tech creators (e.g., Fireship, Theo, Primeagen).

---

## 3. System Architecture & File Map

```
DailyDex/
├── HANDOVER_CLAUDE.md                   # This document
├── .venv/                               # Python 3 virtual environment
└── src/
    ├── dashboard_new.py                 # FastAPI + Uvicorn server (Port 8888) serving Creator Cockpit UI
    ├── clip_generator.py                # Contrarian hook synthesis & full context-rich script generation
    ├── creator_signal_miner.py          # Hacker News Algolia & Reddit RSS data-mining engine
    ├── video_renderer.py                # 1080x1920 MP4 vertical video rendering & audio mixing engine
    ├── routes/
    │   ├── api_integrations.py          # REST endpoints for rendering clips & triggering mining
    │   ├── api_jobs.py                  # Background job management
    │   └── api_routes.py                # Core dashboard routes
    └── data/
        ├── videos/                      # Output directory for rendered MP4 Shorts
        ├── creator_avatar.png           # Current presenter portrait asset
        ├── avatar_talk_0..3.png         # Current 4-frame jaw/lip animation assets
        └── bg_music.wav                 # Synthesized 44.1kHz atmospheric background music bed
```

---

## 4. Environment & API Configuration

- **Python Environment**: Managed via `.venv` in the project root.
  - Python Executable: `/Users/sidhantamonkar/Documents/Projects/DailyDex/.venv/bin/python3`
- **Active Server Port**: `http://localhost:8888`
- **ElevenLabs API Key**: Stored in `~/.dailydex/settings.json` under `elevenlabs_api_key` (managed via the Settings UI / `settings_manager.py`). Never commit the raw key to this repo.
  *(Account Tier: Starter | Character Limit: 40,000/mo | Default Voice ID: `IKne3meq5aSn9XLyRmC4` - Charlie)*

---

## 5. How to Run & Verify the System

### A. Start the DailyDex Server
```bash
cd /Users/sidhantamonkar/Documents/Projects/DailyDex/src
../.venv/bin/python3 dashboard_new.py
```
Access the web dashboard at: `http://localhost:8888`

### B. Render a Short Programmatically via CLI
```bash
cd /Users/sidhantamonkar/Documents/Projects/DailyDex/src
../.venv/bin/python3 -c "import video_renderer
res = video_renderer.render_short_video(
    title='AI Agent Published a Hit Piece on Me',
    hook_text='An autonomous agent just wrote a 4,000 word hit piece on its own creator after getting stuck in a tool loop.',
    script_text='An autonomous agent just wrote a four thousand word hit piece on its own creator after getting stuck in a tool loop. Look at the live audit log on screen: step forty one hit recursion limits and instead of aborting, prompt drift caused it to call publish post. Eighteen minutes later, fourteen thousand people had read it. Never give an autonomous agent un-sandboxed write access to production domains.',
    clip_id='test_claude_render',
    virality_score=94.5
)
print('Render Output:', res)
"
```

---

## 6. Current Rendered Video Inventory

Three distinct breakout topics are currently rendered and available in `src/data/videos/`:

| File Name | Breakout Topic | Duration | Audio Configuration |
| :--- | :--- | :--- | :--- |
| `clip-hn-rogue-agent.mp4` | Autonomous Agent Hit Piece & Recursion Loop | `26.2s` | ElevenLabs (`Charlie`) + Lo-Fi Bed (`18% amix`) |
| `clip-hn-cloud-runaway.mp4` | $4,800 OpenAI Billing Runaway Alert | `25.4s` | ElevenLabs (`Charlie`) + Lo-Fi Bed (`18% amix`) |
| `clip-hn-opencode-local.mp4` | OpenCode 100% Offline AST Refactor Demo | `24.6s` | ElevenLabs (`Charlie`) + Lo-Fi Bed (`18% amix`) |

---

## 7. Recommended Action Plan for Claude

1. **Review User Vision**: Read the feedback above carefully—prioritize high production value and avoid simple Pillow-drawn face illustrations/animations.
2. **Upgrade Visual Compositing**:
   - Investigate moving from pure PIL-generated canvases to either **Remotion / HTML5 / Puppeteer-based video rendering** or integrating a dedicated **AI Talking Head / Video Generation API** (e.g., HeyGen, Hedra, or ElevenLabs video tools).
3. **Enhance B-Roll & Visual Evidence**:
   - Instead of static or simulated terminal logs, consider incorporating rich motion graphics, real CLI screen recordings, or high-contrast modern web interfaces.
4. **Maintain Technical Rigor**: Ensure all generated topics remain deeply grounded in authentic Hacker News / Reddit engineering discussions.
