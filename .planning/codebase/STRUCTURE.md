# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
career-ops/
├── .claude/skills/career-ops/           # Skill router entry point
│   └── SKILL.md                         # Mode detection and dispatch
├── .planning/codebase/                  # GSD mapping documents
├── modes/                               # Instruction files (system layer)
│   ├── _shared.md                       # Global scoring, rules, context
│   ├── _profile.md                      # User customizations (never auto-updated)
│   ├── _profile.template.md             # Template for _profile.md
│   ├── auto-pipeline.md                 # Full JD → report → PDF → tracker pipeline
│   ├── evaluate.md                      # A-G evaluation blocks
│   ├── pdf.md                           # ATS PDF generation
│   ├── scan.md                          # Portal scanner instruction
│   ├── batch.md                         # Batch processing
│   ├── pipeline.md                      # URL inbox processing
│   ├── apply.md                         # Application form assistant
│   ├── contact.md                       # LinkedIn outreach
│   ├── deep.md                          # Company research
│   ├── compare.md                       # Offer comparison
│   ├── tracker.md                       # Tracker display
│   ├── training.md                      # Course/cert evaluation
│   ├── project.md                       # Portfolio project evaluation
│   ├── patterns.md                      # Pattern analysis
│   ├── interview-prep.md                # Interview prep (STAR+R stories)
│   ├── followup.md                      # Follow-up cadence
│   ├── de/                              # German language modes
│   │   ├── _shared.md
│   │   ├── angebot.md                   # Evaluate (German)
│   │   ├── bewerben.md                  # Apply (German)
│   │   └── pipeline.md
│   ├── fr/                              # French language modes
│   │   ├── _shared.md
│   │   ├── offre.md                     # Evaluate (French)
│   │   ├── postuler.md                  # Apply (French)
│   │   └── pipeline.md
│   ├── ja/                              # Japanese language modes
│   │   ├── _shared.md
│   │   ├── kyujin.md                    # Evaluate (Japanese)
│   │   ├── oubo.md                      # Apply (Japanese)
│   │   └── pipeline.md
│   ├── pt/                              # Portuguese language modes
│   │   ├── _shared.md
│   │   ├── oferta.md                    # Evaluate (Portuguese)
│   │   ├── aplicar.md                   # Apply (Portuguese)
│   │   └── pipeline.md
│   └── ru/                              # Russian language modes
│       ├── _shared.md
│       ├── oferta.md                    # Evaluate (Russian)
│       ├── apply.md
│       ├── interview-prep.md
│       └── pipeline.md
├── config/                              # Configuration (user layer)
│   ├── profile.yml                      # Candidate identity (never auto-updated)
│   └── profile.example.yml              # Example template
├── data/                                # User data (never auto-updated)
│   ├── applications.md                  # Master tracker table
│   ├── pipeline.md                      # URL inbox (pending/processed)
│   ├── scan-history.tsv                 # Dedup history (URL → seen date)
│   └── follow-ups.md                    # Follow-up history
├── reports/                             # Evaluation reports (user output)
│   ├── 001-highlevel-2026-04-10.md
│   ├── 002-anthropic-2026-04-10.md
│   └── NNN-{company-slug}-{YYYY-MM-DD}.md
├── output/                              # Generated PDFs (user output, gitignored)
│   ├── cv-christopher-highlevel-2026-04-10.pdf
│   └── cv-{candidate}-{company}-{YYYY-MM-DD}.pdf
├── jds/                                 # Saved job descriptions (user data)
│   └── local:jds/{filename} — referenced in pipeline.md
├── batch/                               # Batch processing (system + output)
│   ├── batch-prompt.md                  # Worker prompt (system layer)
│   ├── batch-runner.sh                  # Orchestrator script (system layer)
│   ├── batch-input.tsv                  # URLs to process (user input)
│   ├── batch-state.tsv                  # Progress tracking (auto-generated, gitignored)
│   ├── tracker-additions/               # TSV files (one per evaluation, gitignored)
│   │   ├── merged/                      # Processed TSVs (moved after merge)
│   │   ├── 001-highlevel.tsv
│   │   └── NNN-{company-slug}.tsv
│   └── logs/                            # Error logs (gitignored)
├── interview-prep/                      # User content
│   ├── story-bank.md                    # Accumulated STAR+R stories
│   └── {company}-{role}.md              # Company-specific interview intel
├── templates/                           # Base templates (system layer)
│   ├── cv-template.html                 # HTML template for PDF generation
│   ├── states.yml                       # Canonical application statuses
│   ├── portals.example.yml              # Example portal config
│   └── ...
├── dashboard/                           # Go TUI dashboard (system layer)
├── fonts/                               # Self-hosted fonts for PDF
├── docs/                                # Documentation
├── examples/                            # Reference examples
├── cv.md                                # Your CV (user layer)
├── portals.yml                          # Portal scanner config (user layer)
├── article-digest.md                    # Proof points (user layer)
├── CLAUDE.md                            # Agent instructions
├── AGENTS.md                            # Codex instructions
├── DATA_CONTRACT.md                     # Layer definitions
├── package.json                         # Dependencies (Node.js)
├── package-lock.json                    # Lockfile
├── .gitignore                           # Excludes batch-state, output/, logs/
│
├── Utility Scripts (system layer):
├── scan.mjs                             # Portal scanner (zero-token)
├── merge-tracker.mjs                    # Merge tracker additions → applications.md
├── dedup-tracker.mjs                    # Fuzzy dedup on company + role
├── verify-pipeline.mjs                  # Integrity checks
├── normalize-statuses.mjs                # Canonical status cleanup
├── generate-pdf.mjs                     # Playwright: HTML → PDF
├── analyze-patterns.mjs                 # Pattern analysis (archetype conversion)
├── followup-cadence.mjs                 # Follow-up status tracking
├── check-liveness.mjs                   # Playwright: verify stale URLs
├── doctor.mjs                           # Health check
├── cv-sync-check.mjs                    # CV freshness vs reports
├── update-system.mjs                    # Version check + apply updates
├── test-all.mjs                         # Test suite
│
└── OpenCode Integration (system layer):
    └── .opencode/commands/
        ├── career-ops.md
        ├── career-ops-evaluate.md
        ├── career-ops-scan.md
        ├── career-ops-batch.md
        ├── career-ops-pipeline.md
        ├── career-ops-pdf.md
        ├── career-ops-apply.md
        ├── career-ops-compare.md
        ├── career-ops-contact.md
        ├── career-ops-deep.md
        ├── career-ops-training.md
        ├── career-ops-project.md
        ├── career-ops-tracker.md
        └── career-ops-followup.md
```

## Directory Purposes

**modes/:**
- Purpose: Instruction files for each skill/workflow
- Contains: Markdown prose with step-by-step prompts, rules, templates
- Key files: `_shared.md` (global scoring), `auto-pipeline.md` (full pipeline), `evaluate.md` (A-G blocks)
- Language variants: `de/`, `fr/`, `ja/`, `pt/`, `ru/` for localized modes

**config/:**
- Purpose: User customization (never auto-updated per DATA_CONTRACT.md)
- Contains: `profile.yml` with name, comp targets, archetypes
- Usage: Loaded at evaluation time to personalize scoring and narrative

**data/:**
- Purpose: User-owned tracker and inbox
- Contains: `applications.md` (master tracker), `pipeline.md` (pending URLs), `scan-history.tsv` (dedup), `follow-ups.md` (follow-up tracking)
- Rule: Never modified by system updates

**reports/:**
- Purpose: Evaluation outputs (numbered sequentially)
- Contains: One markdown report per evaluated offer
- Naming: `{###}-{company-slug}-{YYYY-MM-DD}.md` where `###` is zero-padded sequential number
- Referenced by: `data/applications.md` (report link column)

**output/:**
- Purpose: Generated PDF CVs (gitignored)
- Contains: ATS-optimized PDFs tailored to specific companies
- Naming: `cv-{candidate}-{company}-{YYYY-MM-DD}.pdf`

**batch/:**
- Purpose: Bulk evaluation system
- Contains: `batch-input.tsv` (URLs), `batch-state.tsv` (progress, auto-generated), `tracker-additions/` (TSV files), `logs/` (error logs)
- Workflow: runner processes batch-input → workers generate reports/PDFs/TSVs → merge-tracker consolidates

**interview-prep/:**
- Purpose: Interview preparation (user content)
- Contains: `story-bank.md` (accumulated STAR+R stories across all evaluations), `{company}-{role}.md` (company-specific intel)

## Key File Locations

**Entry Points:**
- `.claude/skills/career-ops/SKILL.md` — Mode router (Claude Code / OpenCode invocation)
- `.opencode/commands/career-ops.md` — OpenCode command mappings

**Configuration:**
- `config/profile.yml` — Candidate identity, comp targets (user layer)
- `portals.yml` — Job portal configuration (user layer)
- `CLAUDE.md` — Agent instructions (never auto-updated)

**Core Logic:**
- `modes/_shared.md` — Scoring system, global rules, archetype definitions
- `modes/evaluate.md` — A-G evaluation blocks
- `modes/auto-pipeline.md` — Full pipeline (extract → evaluate → report → PDF → track)
- `modes/scan.md` — Portal scanner instructions

**Scripts:**
- `scan.mjs` — Automated portal discovery (Greenhouse/Ashby/Lever APIs)
- `merge-tracker.mjs` — Consolidate tracker additions into applications.md
- `generate-pdf.mjs` — Playwright: HTML template → ATS PDF
- `batch-runner.sh` — Orchestrator for parallel worker execution

**Data:**
- `data/applications.md` — Master tracker (source of truth)
- `data/pipeline.md` — Pending URL inbox
- `data/scan-history.tsv` — Dedup history

## Naming Conventions

**Files:**
- Markdown: `{mode-name}.md` (e.g., `evaluate.md`, `auto-pipeline.md`)
- Scripts: `{action}-{object}.mjs` (e.g., `merge-tracker.mjs`, `check-liveness.mjs`)
- Reports: `{NNN}-{company-slug}-{date}.md` where NNN = zero-padded sequential 3-digit number (e.g., `001-highlevel-2026-04-10.md`)
- PDFs: `cv-{candidate}-{company}-{date}.pdf`
- Tracker additions: `{NNN}-{company-slug}.tsv`

**Directories:**
- User layer: lowercase, no special chars (`config/`, `data/`, `output/`)
- Language variants: ISO 639-1 codes (`de/`, `fr/`, `ja/`, `pt/`, `ru/`)
- Batch workflow: singular (`batch/tracker-additions/`, not `tracker_additions/`)

## Where to Add New Code

**New Mode (new skill/workflow):**
1. Create `modes/{mode-name}.md` with step-by-step instructions
2. If mode needs shared context, reference `modes/_shared.md`
3. Register in `.claude/skills/career-ops/SKILL.md` mode table
4. If OpenCode integration needed, add to `.opencode/commands/career-ops-{mode-name}.md`

**New Language Support:**
1. Create directory `modes/{lang_code}/` where lang_code = ISO 639-1 code (e.g., `modes/pt/`)
2. Translate `_shared.md` → `modes/{lang_code}/_shared.md`
3. Translate key modes: `evaluate.md` → `modes/{lang_code}/{mode-name}.md`
4. Add language mode to `config/profile.yml` as optional: `language.modes_dir: modes/{lang_code}`

**New Portal/Company:**
1. Add to `portals.yml` under `tracked_companies` with `careers_url` and optional `api:`
2. If Ashby/Lever/Greenhouse, `scan.mjs` will auto-detect API endpoint
3. Add title filter keywords to `title_filter.positive`/`negative`

**New Tracker Field:**
1. Update `data/applications.md` table header (not recommended — stability is critical)
2. Update `merge-tracker.mjs` parser to handle new column
3. Update `batch/tracker-additions/` TSV schema

**New Utility Script:**
1. Create `{action}-{object}.mjs` in project root
2. Make executable: `chmod +x {action}-{object}.mjs`
3. Follow pattern: `#!/usr/bin/env node`, import fs/yaml, config path handling
4. If it writes to user data, validate against DATA_CONTRACT.md

**New Report Analysis (patterns/followup/etc):**
1. Create mode file: `modes/{analysis-name}.md`
2. Create script: `{analysis-name}.mjs` (reads applications.md, outputs JSON or formatted table)
3. Script should handle missing files gracefully

## Special Directories

**batch/tracker-additions/:**
- Purpose: Temporary TSV files from each evaluation (batch or pipeline)
- Generated: Yes (auto-created by evaluation workers)
- Committed: No (gitignored in `.gitignore`)
- Cleanup: Files moved to `merged/` subdirectory after `merge-tracker.mjs` processes them

**output/:**
- Purpose: Generated PDF CVs
- Generated: Yes (by `generate-pdf.mjs`)
- Committed: No (gitignored)
- Cleanup: Can be safely deleted; will be regenerated on demand

**batch/logs/:**
- Purpose: One log file per batch job (for debugging worker failures)
- Generated: Yes (auto-created by batch-runner)
- Committed: No (gitignored)
- Format: `{report_num}-{id}.log` with JSON status and error messages

**reports/:**
- Purpose: Master evaluation reports (canonical archive)
- Generated: Yes (by evaluate/auto-pipeline modes)
- Committed: Yes (checked into git for audit trail)
- Never delete: Reports are referenced by tracker and are permanent records

**interview-prep/:**
- Purpose: Interview research (user content)
- Contains: `story-bank.md` (auto-appended with STAR+R stories), `{company}-{role}.md` (manually created)
- Auto-appended: Yes (story-bank.md, never overwritten)
- Manual edits: Yes (user may reorganize or delete)

## Data Formats

**applications.md (Tracker):**
```markdown
| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
| 71 | 2026-04-13 | Company Inc | Role Title | 4.2/5 | Applied | ✅ | [071](reports/071-...) | One-line note |
```

**batch/tracker-additions/ (TSV format):**
```
{num}\t{date}\t{company}\t{role}\t{status}\t{score}/5\t{pdf_emoji}\t[{num}](reports/...)\t{notes}
```
**Column order (CRITICAL):** num, date, company, role, status, score, pdf, report, notes (9 columns)

**scan-history.tsv (Dedup tracking):**
```
{url}\t{date-first-seen}\t{company}\t{title}
```

**batch-state.tsv (Progress tracking):**
```
id	url	status	started_at	completed_at	report_num	score	error	retries
1	https://...	completed	2026-...	2026-...	002	4.2	-	0
```

## Configuration Files

**portals.yml (Job portal config):**
- Define `tracked_companies` with `careers_url` and optional `api:` endpoint
- Set `title_filter.positive` and `title_filter.negative` keywords
- Each company must have a `careers_url` or a `scan_query` fallback

**config/profile.yml (Candidate identity):**
- Candidate fields: name, email, location, LinkedIn, portfolio URL
- Target roles and archetypes
- Narrative and superpowers
- Compensation targets and location policy

**modes/_profile.md (User customizations):**
- Target role definitions (custom archetypes, what they "buy")
- Adaptive framing (how to emphasize your strengths for each archetype)
- Exit narrative (1-2 sentences on why you're special)
- Negotiation scripts
- Location policy (remote preference, timezone, on-site flexibility)

---

*Structure analysis: 2026-04-14*
