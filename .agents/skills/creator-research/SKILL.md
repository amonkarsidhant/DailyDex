---
name: creator-research
description: Conducts rigorous, data-backed creator research by mining real audience signals from Hacker News, Reddit, GitHub Trending, and YouTube Outliers to discover high-signal content ideas free from AI filler. Use when researching video topics, finding breakout trends, or analyzing audience pain points for creators.
---

# Creator Research Skill (`creator-research`)

## Purpose
Replaces generic AI brainstorming with grounded, empirical creator research. Every topic, hook, and script outline must originate from verified audience curiosity, active technical debates, breakout open-source releases, or proven outlier metrics.

## Core Research Pillars

### 1. Primary Signal Mining (Zero Hallucination Rule)
Before proposing any content topic, you MUST gather empirical evidence from at least two of the following sources:
- **Hacker News (Algolia API)**: Search top stories (`points > 50`, `num_comments > 20`) within the last 7–14 days. Identify contentious comment threads where engineers are debating trade-offs.
- **Reddit Technical Subreddits** (`r/LocalLLaMA`, `r/machinelearning`, `r/webdev`, `r/selfhosted`): Extract top weekly posts and analyze top comment threads for unsolved frustrations, pricing rants, or architectural bottlenecks.
- **GitHub Trending & Releases**: Identify new repositories or major releases (`v1.0`, `v2.0`) that gained rapid star velocity in the past 7 days.
- **YouTube Outlier Analysis**: Identify videos published in the niche that achieved an **Outlier Score ≥ 3.0x** (views compared to channel median over the last 30 days).

### 2. High-Signal Topic Synthesis Structure
For every discovered topic, structure your findings under this rigorous format:

```markdown
### Topic: [Clear Actionable Title]

#### 1. Empirical Signal Proof
- **Source URL / Discussion**: [Link to HN / Reddit / GitHub / YouTube Outlier]
- **Audience Pain Point**: What specific problem or debate is driving engagement?
- **Engagement Velocity**: e.g., "342 upvotes on HN in 6 hours, 180 comments arguing memory vs latency"

#### 2. The Contrarian Hook (Why Conventional Wisdom is Wrong)
- **Status Quo Belief**: What most people think (e.g., "You need a $5,000 GPU cluster for agents")
- **The Reality / Angle**: What the data/benchmark actually proves (e.g., "Quantized 3B models match 90% of function calling benchmarks on consumer RAM")

#### 3. Real Data Points & Evidence to Show on Screen
- Specific benchmark numbers, pricing comparisons, or architecture diagrams to reference.
- Direct quotes from top community comments to display as visual receipts.

#### 4. Actionable Deliverable / Demo
- Exactly what the creator should test, build, or demonstrate on screen to prove the thesis.
```

### 3. Anti-Patterns (Strictly Forbidden)
- **No Generic Filler Ideas**: Never suggest vague listicles ("Top 5 AI Tools in 2026") without empirical breakout signal proof.
- **No Unverified Claims**: Never invent statistics, benchmarks, or synthetic quotes.
- **No Superficial Overviews**: Every topic must address a concrete technical mechanism, cost trade-off, or architectural pattern.
