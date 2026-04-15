# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**Job Posting APIs (Portal Scanner):**
- **Greenhouse** - Job board API for companies using Greenhouse ATS
  - SDK/Client: Native `fetch()` via Node.js
  - Endpoint: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
  - Auth: None required (public API)
  - Used in: `scan.mjs` (lines 36-37, 61-66)
  - Detection: Auto-detected from `careers_url` or explicit `api:` field in `portals.yml`

- **Ashby** - Job board for startups using Ashby recruiting
  - SDK/Client: Native `fetch()`
  - Endpoint: `https://api.ashbyhq.com/posting-api/job-board/{board-id}?includeCompensation=true`
  - Auth: None required (public API)
  - Used in: `scan.mjs` (lines 43-48)
  - Detection: Auto-detected from `jobs.ashbyhq.com` URL pattern

- **Lever** - Job board API for companies using Lever recruiting
  - SDK/Client: Native `fetch()`
  - Endpoint: `https://api.lever.co/v0/postings/{company-slug}`
  - Auth: None required (public API)
  - Used in: `scan.mjs` (lines 51-57)
  - Detection: Auto-detected from `jobs.lever.co` URL pattern

**Web Scraping (Playwright):**
- **Generic Careers Pages** - Any company with a careers URL
  - SDK/Client: Playwright Chromium headless browser
  - Detection: Career page URLs stored in `portals.yml` `careers_url` field
  - Used in: Implied in scan pipeline (Level 1 fallback if API not available)
  - Liveness checks: `check-liveness.mjs` verifies URLs still active

**Russian Job Boards (Locale-specific):**
- **hh.ru** - Russian job portal API
  - Endpoint: `https://api.hh.ru/vacancies/{id}`
  - Auth: None required
  - Mentioned in: `modes/ru/_shared.md`, `modes/ru/pipeline.md`
  - Status: Documented but not integrated in core `scan.mjs` (locale-specific mode)

## Data Storage

**Databases:**
- Not used; system is file-based

**File Storage:**
- Local filesystem only
- Paths: `data/`, `reports/`, `output/`, `jds/` directories
- No cloud storage integration (AWS S3, Google Drive, etc.)

**Caching:**
- None; all data is source-of-truth in files

## Authentication & Identity

**Auth Provider:**
- None; career-ops is a local, offline tool
- Portal APIs used (Greenhouse, Ashby, Lever) require no authentication
- Optional: User provides LinkedIn/GitHub URLs in `config/profile.yml` for manual reference

**User Identity:**
- Stored locally in `config/profile.yml` (not synced anywhere)
- CV stored in `cv.md` (local markdown file)
- Sensitive info: User handles credentials for their own LinkedIn/GitHub if they choose to use them

## Monitoring & Observability

**Error Tracking:**
- None; errors logged to stdout/stderr only
- Stored in: Script console output

**Logs:**
- Approach: Direct `console.log()` / `console.error()` to stdout
- No log aggregation or centralized logging
- Results captured in:
  - `data/scan-history.tsv` (portal scan results)
  - `data/follow-ups.md` (follow-up history)
  - Report markdown files (`reports/*.md`)

## CI/CD & Deployment

**Hosting:**
- Local machine only (user's laptop or cloud VM)
- Not a hosted service

**CI Pipeline:**
- None explicitly configured
- Health checks available: `npm run doctor`, `npm run verify`, `npm run test-all`
- GitHub Actions (optional): User can set up recurring scans via workflow

**Auto-Update System:**
- `update-system.mjs` checks for releases at `https://github.com/santifer/career-ops/releases/latest`
- Downloads system layer updates from canonical GitHub repo
- Protected: Never touches user data (`DATA_CONTRACT.md` defines separation)

## Environment Configuration

**Required env vars:**
- None explicitly required
- System runs with zero environment variables

**Optional env vars (if user implements):**
- Not documented in codebase
- Any API keys would be user's responsibility (not used by core system)

**Secrets location:**
- Not applicable; system is API-agnostic
- User may store credentials in `.env` (user's responsibility, never committed)
- Strictly user-controlled: Not touched by career-ops code

## Webhooks & Callbacks

**Incoming:**
- None; system is purely pull-based

**Outgoing:**
- None; system does not send webhooks

## Third-Party Data Services

**Reference Data (No Integration):**
Services mentioned in mode files as research references (user manually consults):
- **Glassdoor** - Salary research (mentioned in `modes/_shared.md`, `modes/ru/oferta.md`)
- **Levels.fyi** - Tech compensation data (mentioned in `modes/_shared.md`, `modes/ru/oferta.md`)
- **Blind** - Anonymous tech worker insights (mentioned in `modes/_shared.md`)
- **Habr.com/salary** - Russian tech salary data (mentioned in `modes/ru/oferta.md`)
- **LinkedIn** - Job research and networking (user manually navigates, CV reference in `config/profile.yml`)
- **GitHub** - Portfolio reference (user's `github` field in `config/profile.yml`)

These are NOT API-integrated; users manually research.

## Optional Visual Design Integration

**Canva MCP** - Optional visual CV generation
- Purpose: Alternative to HTML/Playwright PDF generation
- How it works:
  1. User provides `canva_resume_design_id` in `config/profile.yml`
  2. Mode detects it and offers Canva option in `/career-ops pdf`
  3. Implementation: User manually runs Canva export (not automated in this codebase)
  4. Fallback: HTML/Playwright PDF used if no Canva design specified
- Status: Optional; documented in `modes/pdf.md`, not required

## Claude API Integration (Claude Code Platform Only)

**Anthropic Claude**
- Used via: Claude Code interactive environment (not this codebase)
- How: User invokes `/career-ops` slash commands, which load mode files
- Modes loaded: `modes/evaluate.md`, `modes/scan.md`, `modes/pdf.md`, etc.
- This codebase: Provides mode files and utilities for Claude to consume
- Not a direct API call; modes are prompts/instructions for Claude
- Auth: Claude Code handles auth (not this repo)

## Job Posting Verification

**Liveness Check (Playwright):**
- File: `check-liveness.mjs`
- Uses: Playwright Chromium to navigate URL and check for visible job content
- Approach: DOM inspection for apply button visibility
- Returns: `active`, `closed`, `not-found`, `error` classification
- Used before evaluations to confirm posting still live

## Portal Configuration

**Portals Configuration (`portals.yml`):**
Tracks 45+ companies with:
- `careers_url` - Link to company careers page
- `api:` (optional) - Explicit API endpoint
- `enabled:` - Enable/disable scanning
- `title_filter.positive` - Keywords that must match (case-insensitive)
- `title_filter.negative` - Keywords to exclude

Auto-detected APIs:
- Greenhouse: URL pattern `job-boards(?:\.eu)?\.greenhouse\.io`
- Ashby: URL pattern `jobs\.ashbyhq\.com`
- Lever: URL pattern `jobs\.lever\.co`

## Data Flow - Portal Scanning

```
portals.yml (config)
    ↓
scan.mjs (orchestrator)
    ├─→ API detection (detectApi)
    ├─→ Parallel fetch (CONCURRENCY=10)
    │   ├─→ Greenhouse API → parseGreenhouse()
    │   ├─→ Ashby API → parseAshby()
    │   └─→ Lever API → parseLever()
    ├─→ Dedup (seenUrls, seenCompanyRoles)
    ├─→ Title filter (titleFilter)
    └─→ Write output
        ├─→ data/pipeline.md (append new URLs)
        └─→ data/scan-history.tsv (append scan record)
```

## Rate Limiting & Concurrency

- Portal API concurrency: 10 simultaneous requests
- Fetch timeout: 10 seconds
- No rate limiting headers; relies on public API tolerance
- Retry: No automatic retry (single attempt per request)

## Error Handling for External APIs

- HTTP errors: Caught and logged with company name + error message
- Network timeout: 10-second window, then error
- Graceful degradation: Failed company doesn't block others
- Output: Error count reported in summary; successful companies processed

---

*Integration audit: 2026-04-14*
