# 🚀 Feature Spec: YouTube Data & Analytics API v3 Feedback Loop

## Problem Statement
> **How might we** turn DailyDex into an automated, closed-loop creator cockpit by combining YouTube Data API v3, targeted Analytics API v2 metrics, and bulk Reporting API thumbnail telemetry?

---

## Recommended Direction

We will connect `src/youtube_oauth.py`'s existing Google OAuth2 implementation (`yt-analytics.readonly` & `youtube.upload` scopes) directly to the `Pipeline` Kanban board and `src/factory.py` agent generation system. 

When a video moves to `Published` status in DailyDex:
1. **Telemetry Sampling**: DailyDex polls supported targeted Analytics API metrics and stores immutable samples. Thumbnail impressions and CTR require a YouTube Reporting API bulk report or an observed YouTube Studio import; they are never estimated.
2. **The 48-Hour Rescue Engine**: If a video's 48h CTR falls below the channel's rolling median by more than 25%, DailyDex flags it in the Cockpit UI with a **"Low CTR Alert"** and generates a **1-Click Rescue Pack** (3 replacement titles + 2 new visual thumbnail prompts generated via fal.ai Flux).
3. **Agent Calibration Loop**: The `Script Writer` and `Thumbnail Director` agents in `src/factory.py` read historical performance vectors. High-performing hooks and visual styles are weighted higher in system prompts, while lower-performing hook structures are actively anti-prompted.

---

## Key Assumptions to Validate
- [ ] **Data Delay Windows**: Validate Reporting API thumbnail telemetry availability within 48 hours for new uploads.
- [ ] **Title Swap Impact**: Test whether replacing a title/thumbnail 48–72 hours post-publish triggers a statistically significant secondary impression push in YouTube's recommendation system.
- [ ] **Prompt Weight Sensitivity**: Confirm that injecting past performance signals into `src/factory.py` prompts improves generated hook quality without causing repetitive script outputs.

---

## MVP Scope

### In Scope
* **Analytics Sync (`src/orchestrator.py`)**: 6-hourly background sync for supported owner metrics. Reporting API ingestion remains required for automatic thumbnail CTR.
* **Rescue Pack Generator (`src/routes/api_studio.py`)**: API endpoint `/api/studio/rescue-pack` returning 3 alternative titles + 2 thumbnail prompts for any flagged video.
* **Pipeline UI Badges (`frontend/src/PipelineView.tsx` or Cockpit UI)**: Visual indicator (`🔥 Outlier`, `⚡ Healthy`, `🚨 Low CTR - Rescue Available`) per Kanban card.
* **Agent Context Injector (`src/factory.py`)**: Appending top/bottom 3 video hook summaries to the system prompt of the `Script Writer` agent.

### Out of Scope
* **Auto-Applying Title Swaps via API**: Creators must manually approve title/thumbnail changes (preserves creator control and prevents accidental metadata overwrites).
* **Automated YouTube Comment Scraping**: Relying strictly on YouTube Data API v3 structured endpoints to avoid fragile HTML DOM scraping.

---

## Not Doing (and Why)

- **Unauthenticated Web Scraping for Private Metrics** — *Reason:* Web scraping can only retrieve public view counts. Thumbnail CTR is sourced only from observed Studio data or authorized bulk reports.
- **Fully Automated Metadata Updates without Approval** — *Reason:* Replacing a video title automatically could ruin a video that is currently mid-run or conflict with a planned brand campaign.
- **Complex Multi-Variant Multivariate Testing** — *Reason:* Simple 1-click rescue packages solve 90% of the problem with 10% of the UI complexity.

---

## Open Questions

1. **OAuth Quotas**: Does the default YouTube Data API v3 daily quota (10,000 units/day) accommodate 6-hourly telemetry checks for accounts with 50+ published videos, or should we implement rate-limited delta polling?
2. **Fallback for Unauthenticated Users**: For users who haven't completed Google OAuth, should we gracefully fall back to `analytics_sync.py` public view count parsing with reduced functionality?
