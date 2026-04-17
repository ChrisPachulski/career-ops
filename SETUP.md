# Setup

Human-oriented quickstart for a fresh clone. Most of the workflow runs through Claude Code (or OpenCode) — this doc covers the plumbing so the AI agent has a working system to drive.

## Prerequisites

- Node.js 18+ (20+ recommended) -- `node --version`
- Git
- Claude Code, OpenCode, or another Claude-compatible agent (optional but strongly recommended; most flows assume an AI agent reading `CLAUDE.md`)
- Go 1.22+ (optional -- only needed for the TUI dashboard in `dashboard/`)
- Playwright browsers (installed automatically by `npm install`, but the first run of `npm run pdf` may need `npx playwright install chromium`)

## 1. Clone and install

```bash
git clone https://github.com/<fork-owner>/career-ops.git
cd career-ops
npm install
```

## 2. Initialize the database

```bash
npm run init
```

Creates `data/career-ops.duckdb` with all tables, sequences, indexes, and the full-text-search index over report bodies. Idempotent -- safe to rerun after upstream updates.

## 3. Personalize

Three files hold your personal data. They are gitignored, so they won't be clobbered when you pull upstream.

```bash
cp config/profile.example.yml config/profile.yml
cp modes/_profile.template.md modes/_profile.md
cp templates/portals.example.yml portals.yml
```

Then either:
- Hand-edit the three files, **or**
- Open Claude Code in the repo root and let the onboarding in `CLAUDE.md` walk you through it (recommended -- it asks for your CV, target roles, and comp range, then fills them in).

You will also need a `cv.md` at the repo root. The easiest path is to paste your CV into Claude Code and let it convert; otherwise write it yourself in plain markdown with Summary / Experience / Projects / Education / Skills sections.

## 4. First run

With an AI agent:

- "Scan for new offers" -> runs the `scan` mode, populates `pipeline` and `scan_history` tables.
- Paste a JD URL or text -> runs the `auto-pipeline` mode (evaluate + report + PDF + tracker row).
- "What's my pipeline look like?" -> runs `tracker` mode.

Without an AI agent (raw CLI):

```bash
npm run scan                  # portal scan
npm run verify                # DB health check
npm run render                # rebuild data/applications.md from DuckDB
npm run refresh               # rebuild data/dashboard.json
node scripts/db-write.mjs query --sql "SELECT company, role, status, score FROM applications ORDER BY applied_date DESC"
```

## 5. Dashboard (optional)

The Go TUI reads `data/dashboard.json`:

```bash
cd dashboard
go build
./career-ops-dashboard --path ..
```

Status edits in the TUI shell out to `node scripts/db-write.mjs update-status` so you do not need the `duckdb` CLI on PATH.

## Daily use

- Periodically `npm run scan`.
- Paste promising URLs to the agent; it runs `auto-pipeline`.
- After applying, tell the agent "mark Reddit as Applied" (or run `node scripts/db-write.mjs update-status --id=N --status=Applied`).
- Run `npm run verify` once in a while as a sanity check.

## Upstream updates

Upstream can change system-layer files (mode docs, scripts, CLAUDE.md). It will not touch your personal files (cv.md, config/profile.yml, modes/_profile.md, portals.yml, data/, reports/, output/, interview-prep/).

```bash
npm run update:check      # JSON status of upstream vs local
npm run update            # pull + rebase
bash config/reapply-local-patches.sh
```

The reapply script replays fork-specific changes (DuckDB migration, scoring engine, English-mode conversions) on top of the new upstream. If it fails, upstream touched the same lines -- resolve manually and regenerate `config/local-patches.diff`.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `scan.mjs` errors with `data/career-ops.duckdb not found` | Run `npm run init`. |
| Stale `data/.career-ops.lock` blocking writes | A crashed worker left the lock behind. Safe to `rm data/.career-ops.lock` if no `db-write.mjs` is actively running. |
| FTS search returns NULL for new reports | Shouldn't happen -- `insert-report` rebuilds the FTS index. If it does, run `node -e "require('duckdb-async').Database.create('data/career-ops.duckdb').then(db => db.run(\"PRAGMA create_fts_index('reports','id','body','tldr','archetype',overwrite=1)\").then(() => db.close()))"`. |
| `generate-pdf.mjs --application-id=N` prints a command but doesn't register the PDF | By design on Windows -- run the printed `node scripts/db-write.mjs insert-pdf ...` command as the next step. |
| Windows: child Node spawned from inside a Playwright run crashes with `STATUS_STACK_BUFFER_OVERRUN (0xC0000409)` | Known duckdb-async + Playwright interaction. The repo avoids it by using a two-step CLI pattern; don't invoke DuckDB from inside a Playwright-hosting process. |
| Windows: large binary BLOB insert silently exits 127 | Same root cause. This fork deliberately stores PDF metadata only; bytes live in `output/`. |
| `npm run merge` or `npm run normalize` not found | Intentional -- the old TSV-merge and status-normalize scripts were retired in the DuckDB migration. Use `npm run reconcile` instead. |

## Security note

This fork is public. The repo contains fork-specific scripts, mode docs, and config, but **no personal data** -- CV, profile, tracker, reports, PDFs, and the DuckDB file are all gitignored. Check `.gitignore` before committing anything new to `data/`.
