# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** Multi-stage AI-powered job search pipeline with skill-based mode routing, 6-dimensional weighted scoring, and batch processing for at-scale offer evaluation.

**Key Characteristics:**
- Mode-driven orchestration: Each skill/operation (evaluate, scan, batch, pipeline) has its own instruction file in `modes/`
- Layered identity system: Candidate context split into CV (content), profile (targets/comp), and _profile (user customizations)
- Two-layer data contract: System-layer files (auto-updatable) separate from user-layer files (never modified by updates)
- Evaluator-worker pattern: Conductor (Claude) orchestrates Playwright navigation; headless workers (`claude -p`) process offers in parallel
- Real-time verification: All portal scans verified with Playwright before adding to pipeline (no stale URLs)

## Layers

**Skill Layer (Entry points):**
- Purpose: Parse user input and route to the correct mode
- Location: `.claude/skills/career-ops/SKILL.md`
- Contains: Mode detection logic (detect if input is JD, URL, or explicit sub-command)
- Depends on: User invocation; dispatches to mode system
- Used by: OpenCode and Claude Code platforms

**Mode Layer (Instruction/behavior system):**
- Purpose: Each mode defines how to execute one workflow (evaluate, scan, apply, etc.)
- Location: `modes/{mode}.md` + `modes/_shared.md` (system context) + `modes/_profile.md` (user customizations)
- Contains: Step-by-step instructions, prompts, rules specific to that mode
- Depends on: Identity system (cv, profile, _profile)
- Used by: Skill router; also invoked directly by subagents for complex tasks

**Identity Layer (Candidate context):**
- Purpose: Define what is true about the candidate and what they're optimizing for
- Location: `cv.md` (skills/experience), `config/profile.yml` (name/targets), `modes/_profile.md` (archetypes/narrative), `article-digest.md` (proof points)
- Contains: CV text, archetype mappings, comp targets, negotiation scripts, narrative framing
- Depends on: User maintains these files (never auto-updated per DATA_CONTRACT.md)
- Used by: Evaluation engine (blocks A-F), PDF generation, application drafting

**Scoring Engine:**
- Purpose: Compute a 1-5 global score from 6 weighted dimensions
- Location: `modes/_shared.md` (scoring rules, weights, thresholds, blocker gate logic)
- Contains: Dimension definitions (CV Match 25%, Archetype Fit 20%, Comp Alignment 20%, Level Fit 15%, Org Risk 10%, Blockers 10%), blocker gate criteria, score interpretation guidelines
- Depends on: Identity system (targets from profile.yml, archetypes from _profile.md)
- Used by: Evaluate and auto-pipeline modes

**Evaluation Engine (A-G blocks):**
- Purpose: Comprehensive offer analysis with 7 dimensions
- Location: `modes/evaluate.md`
- Contains: Step-by-step instructions for blocks A (summary), B (CV match), C (level strategy), D (comp research), E (customization plan), F (interview prep), G (posting legitimacy)
- Depends on: Scoring engine, identity layer, Playwright/WebFetch for JD extraction and legitimacy signals
- Used by: auto-pipeline and evaluate modes

**Portal Scanner:**
- Purpose: Discover offers from job boards and company career pages
- Location: `modes/scan.md`, `scan.mjs` (zero-token implementation), `portals.yml` (configuration)
- Contains: 3-level discovery strategy (Level 1: Playwright careers_url, Level 2: Greenhouse JSON API, Level 3: WebSearch with site: filters), title filtering, liveness verification
- Depends on: Playwright browser, WebFetch/WebSearch, `portals.yml` configuration
- Used by: scan mode (typically runs as subagent)

**Batch Processor:**
- Purpose: Evaluate multiple offers in parallel using headless workers
- Location: `modes/batch.md`, `batch-runner.sh`, `batch-prompt.md`, `batch/batch-state.tsv`
- Contains: Two-mode orchestration (conductor --chrome for interactive, standalone script for headless), parallel worker invocation, state tracking and resumability
- Depends on: Worker system (claude -p), evaluation engine
- Used by: batch mode; conductor (interactive) or standalone script

**Data Pipeline (Inbox):**
- Purpose: Accumulate and process offer URLs without immediate evaluation
- Location: `modes/pipeline.md`, `data/pipeline.md`
- Contains: Pending/processed URL tracker, JD extraction, auto-numbering of reports, sync checking
- Depends on: Playwright/WebFetch for JD extraction, evaluation engine
- Used by: pipeline mode (processes one or more pending URLs)

**Tracker System:**
- Purpose: Maintain single source of truth for all evaluated offers
- Location: `data/applications.md` (master table), `batch/tracker-additions/` (per-evaluation TSV files), `merge-tracker.mjs`, `dedup-tracker.mjs`, `verify-pipeline.mjs`
- Contains: Application records with number, date, company, role, score, status, PDF path, report link, notes
- Depends on: Canonical states from `templates/states.yml`
- Used by: tracker mode, pattern analysis, follow-up cadence calculation

**PDF Generation:**
- Purpose: Create ATS-optimized candidate CVs tailored to specific job postings
- Location: `modes/pdf.md`, `generate-pdf.mjs`, `templates/cv-template.html`, `fonts/`
- Contains: HTML-to-PDF pipeline via Playwright, keyword injection strategy, localization (letter vs A4), archetype-specific framing
- Depends on: cv.md as source of truth, JD keywords, Playwright
- Used by: auto-pipeline and pdf modes

**Insight Analysis:**
- Purpose: Aggregate patterns and flag opportunities for action
- Location: `analyze-patterns.mjs` (archetype conversion rates, score thresholds), `followup-cadence.mjs` (7d/3d/1d tracking), `check-liveness.mjs` (Playwright verification of stale URLs)
- Contains: Statistical analysis of eval data, follow-up status tracking
- Depends on: applications.md tracker
- Used by: patterns and followup modes

## Data Flow

**Offer Discovery → Evaluation → Tracking:**

1. **Intake** (scan/manual):
   - `scan.mjs` navigates `portals.yml` companies → Greenhouse/Ashby/Lever APIs → title filtering → liveness check via Playwright → append to `data/pipeline.md`
   - Manual: User pastes URL/JD text → routed to auto-pipeline or pipeline mode

2. **Processing** (auto-pipeline or pipeline):
   - Extract JD from URL (Playwright → WebFetch → WebSearch priority)
   - Load identity: read `cv.md`, `config/profile.yml`, `modes/_profile.md`, `article-digest.md`
   - Run evaluation: blocks A-F → compute 6-dimensional score → apply blocker gate → block G legitimacy
   - Save report to `reports/{NNN}-{company-slug}-{date}.md`
   - Generate PDF via `generate-pdf.mjs` (if score >= 3.0)
   - Create tracker TSV to `batch/tracker-additions/{NNN}-{slug}.tsv`

3. **Consolidation** (merge-tracker.mjs):
   - Read all TSV files in `batch/tracker-additions/`
   - Dedup against `data/applications.md` (company + role fuzzy match + report num match)
   - Insert or update rows in applications.md
   - Move merged TSVs to `batch/tracker-additions/merged/`
   - Validate canonical statuses via `templates/states.yml`

4. **Verification** (verify-pipeline.mjs):
   - Check for orphaned reports (files without tracker entries)
   - Validate column order and content
   - Flag missing URLs or reports

**Batch Workflow:**

1. **Setup**:
   - User provides URLs or searches portal (conductor interactive mode)
   - URLs accumulated in `batch-input.tsv` (id, url, source)

2. **Execution**:
   - Conductor reads `batch-state.tsv` (skip completed)
   - For each pending URL:
     - Extract JD (Playwright → DOM)
     - Invoke `claude -p` worker with `batch-prompt.md` (self-contained context)
     - Worker produces: report .md + PDF + tracker TSV
     - Conductor updates batch-state.tsv (status: pending → completed/failed, report_num, score, error, retries)

3. **Resumability**:
   - If process dies: re-run reads state, skips completed, retries failed
   - Lock file (`batch-runner.pid`) prevents double execution
   - Each worker failure isolated; others continue

## Key Abstractions

**Mode:**
- Purpose: Encapsulate one skill/workflow as a reusable instruction set
- Examples: `modes/evaluate.md` (full evaluation), `modes/scan.md` (portal discovery), `modes/batch.md` (bulk processing)
- Pattern: Markdown prose + step-by-step instructions + templates; invoked by skill router or directly by subagents

**Archetype:**
- Purpose: Classify offers into 6 types to adapt framing and proof point selection
- Examples: AI Platform/LLMOps, Agentic/Automation, Technical AI PM, Solutions Architect, Forward Deployed Engineer, Transformation Lead
- Pattern: Detected from JD keywords → maps to `modes/_profile.md` archetype-specific proofs → influences block E (customization) and block F (interview stories)

**Blocker Gate:**
- Purpose: Hard cap on score if any non-negotiable requirement is unmet
- Examples: Citizenship/clearance, specific license, years < 60% of requirement, zero domain experience, geographic impossibility
- Pattern: Checked during scoring; any blocker triggers → Blockers dimension 1.0-2.0 → global score capped at 2.5 max

**Posting Legitimacy (Block G):**
- Purpose: Assess whether an offer is real, active, and worth the candidate's time
- Examples: Posting age, apply button state, JD specificity, layoff news, reposting pattern, salary transparency
- Pattern: Observational signals (not accusations) with legitimate explanations noted; three tiers (High Confidence / Proceed with Caution / Suspicious)

## Entry Points

**SKILL.md (skill router):**
- Location: `.claude/skills/career-ops/SKILL.md`
- Triggers: `/career-ops {mode}` command via Claude Code or OpenCode
- Responsibilities: Parse mode argument → detect auto-pipeline vs explicit sub-command → load mode file + _shared.md → dispatch

**auto-pipeline mode:**
- Location: `modes/auto-pipeline.md`
- Triggers: User pastes JD (text or URL) without explicit sub-command
- Responsibilities: Extract JD (Playwright/WebFetch/WebSearch) → run full evaluation A-G → save report → generate PDF → create tracker TSV → update applications.md

**pipeline mode:**
- Location: `modes/pipeline.md`
- Triggers: User runs `/career-ops pipeline` with pending URLs in `data/pipeline.md`
- Responsibilities: Process each pending URL through auto-pipeline, update pipeline.md (mark as processed), display summary table

**scan mode:**
- Location: `modes/scan.md`, `scan.mjs`
- Triggers: User runs `/career-ops scan`
- Responsibilities: Navigate all enabled companies in `portals.yml` → extract job listings → filter by title → dedup against history → add new URLs to pipeline.md

**batch mode:**
- Location: `modes/batch.md`, `batch-runner.sh`
- Triggers: User runs `/career-ops batch` or `batch-runner.sh`
- Responsibilities: Read batch-input.tsv → spawn parallel workers → collect reports/PDFs/TSVs → merge into applications.md → display summary

**tracker mode:**
- Location: `modes/tracker.md`
- Triggers: User runs `/career-ops tracker`
- Responsibilities: Display applications.md with statistics (total, by status, avg score, PDF %, report %)

## Error Handling

**Strategy:** Fail gracefully; mark in tracker; allow resume.

**Patterns:**

**JD Extraction failures:**
- Playwright timeout → try WebFetch
- WebFetch 403/404 → try WebSearch
- All fail → mark `[!]` in pipeline.md with error note; ask user to paste manually

**Batch worker failures:**
- Worker process dies → conductor catches, marks as `failed` in batch-state.tsv
- Retry logic: read state, skip completed, retry failed up to `--max-retries` (default 2)
- If final failure → log to `logs/{report_num}-{id}.log`, move to next URL

**Liveness check (stale URLs):**
- Level 3 (WebSearch results) verified before adding to pipeline
- Playwright navigates URL → reads content
- No job title + description + Apply control → mark as `Expired` or `Closed`, skip
- Stale URLs never enter the pipeline

**Dedup conflicts:**
- `merge-tracker.mjs` detects duplicate company + role (fuzzy match on role title)
- If duplicate with higher score → update in-place, update report link
- If duplicate with lower score → skip the newer one
- Report: console.log warnings for all duplicates

**Blocker gate (hard stop):**
- If hard blocker detected (e.g., location impossible, cert required, years < 60% of requirement) → set Blockers dimension 1.0-2.0 → cap global at 2.5 max
- Explicitly stated in report: `**Blocker gate active:** {description}. Global capped at 2.5.`

## Cross-Cutting Concerns

**Logging:**
- Approach: Simple console.log for dev/batch scripts; `logging` module for production ETLs
- Patterns: traceback logging in error handlers, JSON status output for machine parsing

**Validation:**
- Approach: Canonical states validated via `templates/states.yml`; TSV format strict (9 columns, specific order)
- Patterns: `merge-tracker.mjs` normalizes non-canonical status (Spanish → English aliases, log warnings)

**Authentication:**
- Approach: None required for public portals; Playwright handles cookies for logged-in sessions
- Patterns: Conductor interactive mode (`--chrome`) logs into employer systems once; workers (`-p`) get preloaded DOM

**Determinism in scoring:**
- Approach: All scores computed from explicit rules in `modes/_shared.md`
- Patterns: Each dimension 1.0-5.0 with one decimal place; global = weighted sum subject to blocker gate; never round up to cross thresholds (3.49 stays below 3.5)

---

*Architecture analysis: 2026-04-14*
