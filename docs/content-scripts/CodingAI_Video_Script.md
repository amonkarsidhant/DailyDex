# Coding AI — The Full Script

**Target runtime:** 14–18 min

---

## COLD OPEN (30s verbatim)

> "Everyone says AI is coming for your job. They're wrong. AI already replaced your job — the problem is you're still writing code like it's 2023. SWE-bench verified scores have jumped from 3% to over 70% in two years. The top agents now solve 7 out of 10 real GitHub issues autonomously. If your workflow hasn't changed since ChatGPT launched, you're not 'being careful' — you're being outsourced to someone who already switched."

---

## SECTION 1 — The Great Disconnect: Benchmarks vs. Reality (4-5 min)

- The numbers are insane — but deceptive. Walk the SWE-bench timeline:
  - **April 2024:** SWE-bench introduced. Best score: ~3% (unmodified agents).
  - **Aug 2024:** Devin scores 13.8% with full pipeline.
  - **Feb 2025:** Claude 3.5 Sonnet + agentic loop hits 49%.
  - **June 2026:** Current SOTA crosses 72% on SWE-bench Verified.
- **Real repo to cite:** `princeton-nlp/SWE-bench` — 2,294 real GitHub issues from 12 popular Python repos like django/django, sympy/sympy, scikit-learn/scikit-learn.
- But here's the trap: SWE-bench tests bug-fixing, not greenfield engineering. A 72% bug-fix rate doesn't mean AI builds production systems.
- **The stat that matters:** Cognition's internal eval shows Devin autonomously completes ~35% of "junior engineer" tickets end-to-end. That's real, but it means 65% still need human intervention.
- Where the benchmark-to-reality gap hurts most: **context window management.** In SWE-bench, the agent gets the failing test and the issue text. In real codebases, tickets are vague, requirements shift mid-stream, and you have 15 microservices to reason across.
- **Key insight:** The leaders — Cursor Tab, Copilot Agent Mode, Claude Code — have converged on the same architecture: a fast-edit LoRA for completions + a heavy reasoning model (Opus-level) for planning. The delta is now in **tooling ergonomics**, not model capability.
- Close the section by naming the gap: "If you just use autocomplete, you're using 5% of what 2026 AI can do. The unlock is in the agentic loop."

---

## SECTION 2 — Building a Real Feature: The Demo Walkthrough (5-6 min)

> *On-screen: Terminal + browser, real-time. Build a small feature end-to-end.*

- **The task:** Add pagination with cursor-based keyset pagination to a FastAPI app that currently loads everything into memory. Real problem, real codebase — not a tutorial todo app.
- **Stack shown:** FastAPI + SQLAlchemy 2.0 + PostgreSQL.
- **Tool:** Claude Code (or Cursor Agent). Show the exact command/prompt:

  ```
  "Add keyset pagination to the /api/users endpoint.
   Current code in src/routes/users.py does SELECT * with no limit.
   Use created_at + id as the cursor columns.
   Return next_cursor in the response body.
   Keep it backwards-compatible — if no cursor param is sent, return the first page."
  ```

- **Walk through what the agent does, step by step:**
  1. Reads `src/routes/users.py` and the User model.
  2. Generates the migration (Alembic — show the revision file).
  3. Rewrites the endpoint with `WHERE (created_at, id) > (:cursor_created, :cursor_id)` pattern.
  4. Adds `total_count` via a separate `COUNT(*)` — and the agent *correctly* wraps it in a CTE to avoid race conditions.
  5. Writes tests using pytest + httpx `AsyncClient`.
  6. Runs `pytest`, hits a type issue with `cursor_params` being `Optional[str]` vs `str`, self-heals in one shot.
- **Total time from prompt to green tests:** ~3 minutes.
- **Show the diff** — highlight what the agent got right vs. wrong:
  - **Right:** Keyset pagination is correct, query uses index properly, migration is reversible.
  - **Wrong:** It assumed `created_at` is timezone-aware but the model uses naive UTC. One manual fix needed.
- **Real talk:** "The agent wrote production-quality pagination in 3 minutes. I spent more time writing this script than fixing that timezone bug."
- **Repo reference:** Open source the demo as `dailydex/keyset-pagination-demo` so viewers can clone and reproduce.
- **Mention Aider's `--architect` mode** as an alternative workflow: one model plans, another edits. "Cursor and Claude Code are the default, but Aider's architect/edit split is criminally underrated for complex refactors."

---

## SECTION 3 — The Contrarian Take: What You Should NOT Let AI Touch (3-4 min)

- Every creator tells you "let AI write everything." Here's what they don't tell you.
- **Thing #1 — Database migrations in production.** AI has no concept of your data shape. It'll happily suggest a migration that takes a 2TB table down for 45 minutes. **Real example:** The `add NOT NULL column with default` mistake. AI writes `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT ...` — which is fine in Postgres 11+ but locks the table in MySQL 8. The agent doesn't know which DB you're on unless you spoon-feed it the schema.
- **Thing #2 — Security boundaries.** In 2025, Sysdig published research showing 23% of Copilot-generated SQL queries had SQLi vulnerabilities. The models have improved, but agentic loops amplify bad patterns. If the agent generates a SQL query that concatenates user input — and you don't catch it — you now have an exploitable code path. **The agent doesn't run `sqlmap` on its own output.**
- **Thing #3 — Dependency choices.** AI loves `pip install [hot new library]`. In a study by Endor Labs (Jan 2026), AI-suggested packages were 3.7x more likely to include transitive dependencies with known CVEs vs. human-chosen equivalents. The model optimizes for "this solves the problem" — not "this is maintained, vetted, and secure."
- **Thing #4 — Business logic with money on the line.** Pricing calculations, billing tiers, discount stacking — AI gets the syntax right but misses the business rules. One Y Combinator startup in W25 shipped an AI-generated pricing module that let users stack unlimited promo codes. Cost them ~$40K before they caught it.
- **The principle:** Use AI for implementation, not specification. "AI writes the *how* — you write the *what* and the *why not*."
- **Real tooling:** Show `continue.dev` with codebase-wide RAG as the bridge — it lets you define rules like "never use `DEFAULT` in ALTER COLUMN" and "prefer `suppress` over `# noqa`" as project-wide constraints.

---

## OUTRO + CTA (1 min verbatim)

> "Here's the bottom line. AI in 2026 writes better code than most junior engineers I've interviewed — but it has zero judgment. The winners aren't the people who let AI code everything. The winners are the ones who set the guardrails, check the outputs, and focus on the 30% that actually requires human thinking.
>
> If you want the full demo repo — keyset pagination, with the timezone bug left in so you can see the exact diff — I'll link it in the description. Also dropping the Continue.dev config file I use across all my projects, with the security rules baked in.
>
> Comment: what's one piece of code you'll never let AI write for you? I read every response.
>
> Subscribe if you want the video where I test all five 2026 coding agents on the same production issue — spoiler: one of them deletes the database. See you next week."

---

## Production Notes

- **Total runtime estimate:** ~16 min (COLD OPEN: 30s, Section 1: 4:30, Section 2: 5:30, Section 3: 3:45, Outro: 1:00)
- **B-roll throughout Section 2:** side-by-side terminal + Claude Code/Cursor UI with the prompt visible
- **Section 3 visual:** split screen — AI-generated code on left, the `psql`/`EXPLAIN ANALYZE` output showing the lock on right
- **Thumbnail idea:** Terminal split — green checkmark on one side, red "MIGRATION LOCK" on the other. Face-cam reaction middle.
