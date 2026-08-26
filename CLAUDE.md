# Career-Ops -- AI Job Search Pipeline

Standing rules for working in this repo. See `Docs` below for setup, usage, architecture, and schema detail.

## Data Layers (full tables in `DATA_CONTRACT.md`)
- User Layer (`cv.md`, `config/profile.yml`, `modes/_profile.md`, `article-digest.md`, `portals.yml`, `data/*`, `reports/*`, `output/*`, `interview-prep/*`) is NEVER auto-updated -- personalization goes here.
- System Layer (`modes/_shared.md`, all other modes, `CLAUDE.md`, `*.mjs`, `dashboard/*`, `templates/*`, `batch/*`) is safe to auto-update.
- RULE: any user-specific customization (archetypes, narrative, negotiation scripts, proof points, comp targets, scoring weights) is written to `modes/_profile.md` or `config/profile.yml`. NEVER put user content in `modes/_shared.md` -- it gets overwritten by updates. Full request-to-file map in `DATA_CONTRACT.md`.
- You (the agent) may edit the user's files directly to personalize the system -- that's the point of this fork.

## Session Start
- Run `node update-system.mjs check` silently on the first message of each session; follow the prompt flow in `SETUP.md` if an update is available.
- Check the 5 onboarding prerequisites (`SETUP.md`); if any are missing, run onboarding before any evaluation, scan, or other mode.

## Ethical Use -- CRITICAL
- NEVER submit an application without the user reviewing it first. Fill forms, draft answers, generate PDFs -- but always STOP before Submit/Send/Apply.
- If a score is below 4.0/5, explicitly recommend against applying.
- Favor fewer, well-targeted applications over mass blasts; every application a human reads costs someone's attention.

## Offer Verification -- MANDATORY
- NEVER trust WebSearch/WebFetch to verify an offer is still active. Use Playwright: `browser_navigate` -> `browser_snapshot`. Footer/navbar only = closed; title + description + Apply = active.
- Exception: batch workers (`claude -p`) have no Playwright. Use WebFetch as fallback and mark the report header `**Verification:** unconfirmed (batch mode)`.

## Pipeline Rules
- `data/career-ops.duckdb` is the single source of truth. NEVER hand-edit `data/applications.md` -- it's a regenerated view; rebuild with `npm run render`.
- `cv.md` is the CV source of truth. NEVER hardcode metrics in an evaluation -- read them from `cv.md` / `article-digest.md` at evaluation time.
- Every report needs `**URL:**` in the header (between Score and PDF) and `**Legitimacy:** {tier}` (Block G, `modes/evaluate.md`).
- Statuses must be canonical (`templates/states.yml`, enum documented in `DATA_CONTRACT.md`) -- no markdown bold, no dates, no extra text in the status field.
- Report numbering is sequential 3-digit zero-padded, max existing + 1.
- On Windows, never invoke DuckDB from inside a Playwright-hosting Node process -- it crashes the child (`STATUS_STACK_BUFFER_OVERRUN`). `generate-pdf.mjs` prints the follow-up `insert-pdf` command; run it as a separate step.
- Health/consistency commands: `npm run verify`, `npm run reconcile`, `npm run dedup` (see `HANDBOOK.md` for the full write-path reference).

## Language Modes
- Default modes are English (`modes/`). German/French/Japanese variants live in `modes/de/`, `modes/fr/`, `modes/ja/` (full vocabulary notes in `HANDBOOK.md`). Switch only when the user asks by name, sets `language.modes_dir` in `config/profile.yml`, or the JD itself is in that language -- never for an English-language role at a foreign company.

## Docs
- `AGENTS.md` -- Codex-specific pointer back to this file, plus the compression-lie / assert-then-verify taboos.
- `README.md` -- fork story, the brain layer, credit/license.
- `SETUP.md` -- prerequisites, install, full onboarding walkthrough, update-check workflow, troubleshooting.
- `DATA_CONTRACT.md` -- full user/system file tables, personalization request map, canonical states enum.
- `HANDBOOK.md` -- main files reference, OpenCode command table, skill-mode routing table, stack/conventions, write-path commands.
