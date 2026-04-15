# Technology Stack

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- JavaScript (Node.js ES6+) - All automation scripts, utilities, and CLI tools
- YAML - Configuration files (`config/profile.yml`, `portals.yml`, `templates/states.yml`)
- HTML/CSS - CV template design (`templates/cv-template.html`)
- Markdown - Data storage and mode definitions

**Secondary:**
- Plain text - Bash shell scripts for batch operations (`batch/batch-runner.sh`)

## Runtime

**Environment:**
- Node.js 18+ (required for ES6 modules, async/await, native fetch)
- Chromium (via Playwright) for headless rendering

**Package Manager:**
- npm
- Lockfile: `package-lock.json` (present)

## Frameworks

**Core Automation:**
- Playwright 1.59.1 - Headless Chromium browser for PDF generation, web scraping, and liveness checks
- js-yaml 4.1.1 - YAML parsing for configuration files

**No frameworks used for:**
- Web server (Node.js native HTTP only for local file serving)
- Database (file-based: Markdown and TSV for all data)
- Frontend (static HTML templates, no React/Vue/Angular)

## Key Dependencies

**Critical:**
- `playwright` 1.59.1 - Headless browser automation
  - Used in: `generate-pdf.mjs` (HTML → PDF with font embedding), `check-liveness.mjs` (verify job posting still active), `scan.mjs` (portal scraping fallback)
  - Why it matters: Core dependency for PDF generation and web verification

- `js-yaml` 4.1.1 - YAML configuration parsing
  - Used in: `scan.mjs`, `merge-tracker.mjs`, all mode files
  - Why it matters: All user configuration reads through this library

**Infrastructure:**
- None explicitly listed; system uses Node.js built-ins for file I/O, path resolution, child process execution

## Configuration

**Environment:**
- No .env file required; configuration is explicit in YAML files
- System passes configuration via command-line flags and file paths
- No secrets in code; users store credentials externally (if needed for third-party APIs)

**Build:**
- No build step; runs directly as Node.js scripts
- Fonts embedded in `fonts/` directory (woff2, TTF formats)
- HTML template in `templates/cv-template.html`

**Configuration Files:**
- `config/profile.yml` - User profile (name, email, target roles, compensation, narrative)
- `portals.yml` - Job portal tracking configuration (title filters, company list, APIs)
- `templates/states.yml` - Canonical application status definitions
- `package.json` - NPM metadata and scripts

## Platform Requirements

**Development:**
- Node.js 18+ (ships with npm and `node` binary)
- Bash shell (for running scripts)
- Git (for version control and auto-updates)
- Nix (optional, via `flake.nix` for reproducible environment)

**Production (CLI Execution):**
- Node.js 18+
- Chromium (auto-installed by Playwright)
- 200MB+ disk space (for node_modules, fonts, reports)
- Network access (for portal APIs: Greenhouse, Ashby, Lever)

**Optional Integrations:**
- Anthropic Claude API (via Claude Code platform, not directly in this codebase)
- Canva MCP (optional, for visual CV generation via `canva_resume_design_id`)

## Scripts (npm and Node)

**Available npm scripts** (`package.json`):
```
npm run doctor          → Health check (Node.js, fonts, playwright, CV sync)
npm run verify          → Validate applications.md pipeline integrity
npm run normalize       → Normalize status values to canonical forms
npm run dedup           → Remove duplicate entries from tracker
npm run merge           → Merge batch tracker additions into applications.md
npm run pdf             → Generate PDF from HTML (entrypoint: generate-pdf.mjs)
npm run sync-check      → Verify CV ↔ config/profile.yml consistency
npm run update:check    → Check for system updates
npm run update          → Apply system updates (system layer only)
npm run rollback        → Rollback last update
npm run liveness        → Verify job postings still active
npm run scan            → Scan portals for new offers
```

**Standalone scripts** (run with `node <script>`):
- `analyze-patterns.mjs` - Parse rejection patterns and generate recommendations
- `check-liveness.mjs` - Playwright: verify URLs are live
- `cv-sync-check.mjs` - Validate CV ↔ profile.yml alignment
- `dedup-tracker.mjs` - Remove duplicate applications
- `doctor.mjs` - System health check
- `followup-cadence.mjs` - Follow-up tracking and cadence calculator
- `generate-pdf.mjs` - Convert HTML → PDF with ATS normalization
- `liveness-core.mjs` - Core liveness detection logic
- `merge-tracker.mjs` - Merge batch tracker additions (handles dedup, status validation)
- `normalize-statuses.mjs` - Normalize status values
- `scan.mjs` - Multi-API portal scanner (Greenhouse, Ashby, Lever)
- `test-all.mjs` - Run all validation checks
- `update-system.mjs` - Safe auto-updater (system layer only, never touches user data)
- `verify-pipeline.mjs` - Validate applications.md structure and status values

## Data Storage

**File-based (no database):**
- `data/applications.md` - Main tracker (markdown table: 9 columns)
- `data/pipeline.md` - Pending URLs inbox
- `data/scan-history.tsv` - Dedup history (portal scan results)
- `data/follow-ups.md` - Follow-up attempt log
- `batch/tracker-additions/*.tsv` - Batch evaluation results (9-column TSV)
- `reports/{###}-{slug}-{YYYY-MM-DD}.md` - Evaluation reports (A-F + G blocks)
- `jds/` - Local job description files (markdown or raw HTML)

**Output:**
- `output/` (git-ignored) - Generated PDFs and temporary files

## Version Management

**Current Version:** 1.0.0 (stored in `VERSION` file)

**Update Strategy:**
- System updates via `update-system.mjs` (GitHub releases)
- User data protected during updates (DATA_CONTRACT.md enforces separation)
- Rollback capability via git history

---

*Stack analysis: 2026-04-14*
