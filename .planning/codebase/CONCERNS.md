# Codebase Concerns

**Analysis Date:** 2026-04-14

## Tech Debt

### 1. Interview-Prep Mode Not Implemented

**Issue:** `interview-prep` mode is documented in CLAUDE.md (SKILL.md routing table) and `.claude/skills/career-ops/SKILL.md` lists it as an invocable mode, but no implementation exists.

**Files:** 
- `.claude/skills/career-ops/SKILL.md` (line 31-32: routes `interview-prep` to `modes/interview-prep.md`)
- `modes/interview-prep.md` (exists, 50 lines)
- `interview-prep/` directory (only contains `story-bank.md`)

**Impact:** When user invokes `/career-ops interview-prep` or `/career-ops-interview-prep` (OpenCode), the skill router expects to load `modes/interview-prep.md` but the prompt is minimal. Users will not get the full company-specific interview prep flow described in CLAUDE.md (Step 2, "Preps for interview at specific company").

**Fix approach:** Expand `modes/interview-prep.md` with:
- Prompt for company name + role
- Load company-specific intel from `interview-prep/{company}-{role}.md` if it exists
- Generate STAR+R story frames from `interview-prep/story-bank.md`
- Output company-specific interview brief with: key technical areas, culture signals, likely questions, proof point matching

### 2. Followup Mode Not Documented in Package.json

**Issue:** `modes/followup.md` exists and is referenced in SKILL.md routing, but package.json does not have a corresponding npm script.

**Files:**
- `modes/followup.md` (exists)
- `package.json` (missing `followup` command)
- `followup-cadence.mjs` (exists but requires manual execution via `node`)

**Impact:** Users cannot run `npm run followup` — they must manually invoke `node followup-cadence.mjs`. Inconsistent with other modes that have npm shortcuts.

**Fix approach:** Add to `package.json` scripts: `"followup": "node followup-cadence.mjs"`

### 3. Missing Batch Processor Runtime Script

**Issue:** `batch/` directory contains `batch-prompt.md` and `batch-runner.sh` (listed in update-system.mjs SYSTEM_PATHS) but the batch execution pipeline is not tested end-to-end.

**Files:**
- `batch/batch-prompt.md` (system layer)
- `batch/batch-runner.sh` (system layer, not in package.json)
- `batch/tracker-additions/` (working directory, has 79 merged files)
- `batch/logs/` (exists, likely for outputs)

**Impact:** Batch processing relies on a shell script + Claude Code subagents, but there's no validation that:
1. The batch runner can actually spawn agents
2. TSV output format from batch workers matches merge-tracker.mjs expectations
3. Error handling when a worker fails mid-batch

**Fix approach:** 
- Add `test-batch.mjs` that simulates batch processing (mock worker output + merge)
- Document batch workflow in CLAUDE.md's batch section
- Add retry logic for failed workers (currently missing)

## Known Bugs

### 1. Scan History Dedup May Fail with Malformed URLs

**Issue:** `scan.mjs` dedup logic loads URLs from three sources (scan-history.tsv, pipeline.md, applications.md) but doesn't normalize/canonicalize URLs before comparing.

**Files:** `scan.mjs` (lines 134-164)

**Trigger:** Two URLs pointing to the same job but with different protocols (`http://` vs `https://`), query param order, or trailing slashes will not be recognized as duplicates.

**Workaround:** Currently none. Scanner will append duplicate URLs to pipeline.

**Fix approach:** Canonicalize URLs before dedup — strip protocol, normalize params, remove trailing slashes.

### 2. Merge-Tracker TSV Column Detection Heuristic May Misfire

**Issue:** `merge-tracker.mjs` (lines 137-159) uses heuristic pattern matching to detect whether columns 4-5 are (status, score) or (score, status). The heuristic can fail on edge cases.

**Files:** `merge-tracker.mjs` (lines 139-159)

**Trigger:** If a status value matches the score regex (e.g., `3.0` typed as text in status field) OR if both columns look like status, the heuristic picks the first match, which may be wrong.

**Workaround:** Ensure TSV files strictly follow: `num\tdate\tcompany\trole\tstatus\tscore\tpdf\treport\tnotes`

**Fix approach:** Add explicit column header detection — look for TSV first line with labels like "num,status,score" and use that to determine column order. Fall back to heuristic only if header is missing.

### 3. Playwright Page Leak in check-liveness.mjs

**Issue:** `check-liveness.mjs` opens a single page and reuses it for all URLs. If a URL navigation hangs or times out partway through, the page object may be in an invalid state for the next URL.

**Files:** `check-liveness.mjs` (lines 90-105)

**Trigger:** Third URL in a batch times out — subsequent URLs may fail or return incorrect results because page state is corrupted.

**Workaround:** Run check-liveness on one URL at a time.

**Fix approach:** Create a fresh page for each URL (or reuse but add `await page.reload()` between checks), or wrap in try/catch per URL with page recovery logic.

## Security Considerations

### 1. No API Rate Limiting or Backoff in scan.mjs

**Issue:** `scan.mjs` fetches from Greenhouse, Ashby, and Lever APIs with FETCH_TIMEOUT_MS (10 seconds) but no exponential backoff or rate limit handling.

**Files:** `scan.mjs` (lines 106-118, 320)

**Risk:** If IP is rate-limited or blocked, script fails silently (error in the errors array) but does not retry. Mass scanning portals could trigger IP blocks.

**Current mitigation:** CONCURRENCY = 10 (limits parallel requests), but no per-company backoff.

**Recommendations:**
- Add exponential backoff (delay 1s → 2s → 4s) per API on 429 responses
- Log when IP is rate-limited and suggest user wait before next scan
- Add `--slow` flag for polite scanning (1 req/sec per API)

### 2. No Input Validation on scan.mjs Company Names

**Issue:** `scan.mjs` passes company names directly to console output and file writes without sanitization.

**Files:** `scan.mjs` (lines 313, 348)

**Risk:** If a malicious YAML entry has shell metacharacters in the company name, it could be echoed to logs. Low risk (controlled YAML), but poor practice.

**Recommendations:** Sanitize company names for logging (remove newlines, tabs, control characters).

## Performance Bottlenecks

### 1. Sequential Processing in check-liveness.mjs

**Issue:** `check-liveness.mjs` checks URLs one at a time (lines 97: "Sequential — project rule").

**Files:** `check-liveness.mjs` (lines 97)

**Problem:** Checking 20 URLs takes ~300 seconds (15s timeout × 20). No parallelization.

**Current capacity:** ~4-6 URLs per minute (rule comment suggests deliberate design).

**Improvement path:** 
- Option A: Use Playwright's browser pooling (3-5 pages in parallel) to check URLs concurrently while respecting Playwright's internal limits
- Option B: Add `--parallel N` flag to tune concurrency per user preference
- Note: Rule says "never Playwright in parallel" — verify if this is security/stability constraint or just best practice

### 2. Full Applications.md Table Parse on Every Script

**Issue:** Every utility script (merge-tracker.mjs, dedup-tracker.mjs, verify-pipeline.mjs, normalize-statuses.mjs) parses the entire applications.md file by splitting on `|` and filtering.

**Files:** Multiple scripts parse lines 23-75

**Problem:** At 74 entries (currently), this is <1ms. At 500+ entries (after 12+ months of job search), parsing becomes measurable. Each script re-parses from scratch.

**Improvement path:**
- Refactor into shared `parse-applications.mjs` module used by all scripts
- Consider caching parsed JSON in `.cache/applications.json` with mtime check
- For now: acceptable, but flag if tracker grows beyond 200 entries

## Fragile Areas

### 1. Data Layer Layout Ambiguity

**Issue:** Multiple scripts (merge-tracker.mjs, dedup-tracker.mjs, verify-pipeline.mjs, normalize-statuses.mjs) check for `data/applications.md` vs `applications.md` in repo root (lines 24-26 in merge-tracker.mjs).

**Files:** Each utility has this pattern:
```js
const APPS_FILE = existsSync(join(CAREER_OPS, 'data/applications.md'))
  ? join(CAREER_OPS, 'data/applications.md')
  : join(CAREER_OPS, 'applications.md');
```

**Why fragile:** The system shipped with applications.md in root (legacy), but CLAUDE.md + package.json assume it's in `data/`. If a user copies an old setup, scripts will silently use the wrong file.

**Safe modification:** 
- Standardize on `data/applications.md` as THE location
- Update CLAUDE.md step 4 to require this layout
- Add doctor.mjs check: "applications.md must be in data/"

**Test coverage gap:** verify-pipeline.mjs passes (applications.md in data/), but no test for the legacy case.

### 2. States.yml Never Enforced

**Issue:** `verify-pipeline.mjs` reads CANONICAL_STATUSES hardcoded (lines 32-35) instead of loading from `templates/states.yml`.

**Files:**
- `verify-pipeline.mjs` (hardcoded list)
- `templates/states.yml` (exists, should be source of truth per CLAUDE.md)
- `merge-tracker.mjs` (also hardcoded list, lines 33)

**Why fragile:** If states.yml is updated, the scripts won't see the change. Canonical state list is duplicated in 3 places (verify-pipeline, merge-tracker, normalize-statuses).

**Safe modification:** Load states.yml at script start (already using js-yaml in package.json), fail loudly if parsing fails.

**Test coverage gap:** test-all.mjs checks states.yml exists (line 140) but doesn't verify scripts read from it.

### 3. Report Number Collision Risk in Batch Processing

**Issue:** merge-tracker.mjs line 283 assigns entry numbers with logic: `entryNum = addition.num > maxNum ? addition.num : ++maxNum`. If two batch workers both generate report #50 for different companies, the second one will be renumbered silently.

**Files:** `merge-tracker.mjs` (lines 280-288)

**Trigger:** Parallel batch workers run `/career-ops evaluate` independently, both generate report #50, both write to `batch/tracker-additions/{50}-{company}.tsv`.

**Workaround:** Batch runner must enforce unique report numbers across workers (not documented).

**Fix approach:** Report numbering should be centralized — either:
1. Batch runner pre-allocates block of report numbers to each worker (e.g., worker 1 gets 100-149, worker 2 gets 150-199)
2. Merge script uses a lock file (`merge.lock`) to prevent concurrent merges
3. Merge step is always run serially by the orchestrator

## Test Coverage Gaps

### 1. End-to-End Pipeline Untested

**Issue:** No test verifies the full pipeline: scan → pipeline.md → merge → applications.md → reports/.

**What's tested:**
- Individual script syntax (test-all.mjs)
- Liveness classification (test-all.mjs, 6 cases)
- Data contract files exist (test-all.mjs)

**What's NOT tested:**
- A real scan → real pipeline append → real merge
- PDF generation (generate-pdf.mjs skipped in tests)
- Batch processing with mock evaluations
- Applications.md schema compliance (rows, columns, format)

**Risk:** Breaking change in report format would not be caught until user runs full pipeline.

**Priority:** Medium — affects quality but rare workflow.

### 2. Playwright Upgrade Risk

**Issue:** Package.json pins `playwright: ^1.59.1`. No tests verify Playwright API compatibility.

**Files:** `package.json` (line 35)

**Risk:** Major version bump (e.g., Playwright 2.x) could break:
- `chromium.executablePath()` (used in doctor.mjs)
- `page.goto()` + `page.waitForTimeout()` (used in check-liveness.mjs)
- `page.pdf()` (used in generate-pdf.mjs)
- Font loading via `file://` URLs

**Current mitigation:** Caret `^` allows patch/minor updates, blocks major. Acceptable.

**Improvement:** Add e2e smoke test: generate 1-page PDF, verify output exists and has size > 10KB.

## Missing Critical Features

### 1. No Bulk Update Tool for Applications.md

**Issue:** Users cannot bulk-edit applications.md (e.g., "mark all Discarded entries as SKIP"). Must edit manually.

**What exists:** dedup, normalize, merge, verify scripts.

**What's missing:** bulk-update.mjs or similar to support operations like:
- `node bulk-update.mjs --company Anthropic --set-status "Applied"`
- `node bulk-update.mjs --status "Evaluated" --older-than "2026-02-01" --set-status "Discarded"`

**Impact:** Low (rarely needed), but user must edit markdown directly.

### 2. No Report Template Generator

**Issue:** Report files (e.g., `reports/001-highlevel-2026-04-10.md`) are manually created. No script generates the markdown structure from a JD + evaluation.

**What exists:** Report files in `reports/`, modes/evaluate.md has the structure (A-F blocks).

**What's missing:** generate-report.mjs that:
- Takes JD text + evaluation results
- Creates markdown report with all blocks
- Outputs to `reports/{num}-{slug}-{date}.md`

**Impact:** Moderate — the `/career-ops evaluate` skill in Claude Code probably generates reports, but the system layer doesn't automate it. Users relying on pure CLI would have to write reports manually.

## Scaling Limits

### 1. Applications.md Table Size Limit

**Current capacity:** 74 entries, easily editable and parseable.

**Limit:** ~500 entries. Beyond this:
- Markdown table becomes unwieldy (can't scroll easily in VS Code)
- Parse time becomes measurable (ms, not µs)
- Merge/dedup operations slow down linearly

**Scaling path:** At 200 entries, consider:
- Split into `data/applications-{YYYY-MM}.md` monthly archives
- Or migrate to JSON lines format (`applications.jsonl`), keep markdown for browsing

### 2. Batch Worker Concurrency

**Current design:** Batch runner spawns N subagents in parallel, each writes to `batch/tracker-additions/{num}-{company}.tsv`.

**Limit:** No hard limit, but:
- Each agent consumes ~50-100MB RAM (Claude Code context)
- Merge step is serialized (one merge at a time)
- If 10 workers finish simultaneously, merge processes 10 files sequentially

**Scaling path:** For 100+ parallel workers, implement:
- Worker pool (queue) instead of all-at-once
- Merge batching (merge every 10 files, not one at a time)
- Async merge via background job

## Dependencies at Risk

### 1. Playwright Installation Fragility

**Issue:** `doctor.mjs` checks if `chromium.executablePath()` exists (line 48), but this can fail silently on system without required libraries.

**Files:** `doctor.mjs` (lines 44-63)

**Risk:** On Linux without libdeps, Playwright installs but chromium executable path doesn't exist. doctor.mjs will report "Chromium not installed" and tell user to `npx playwright install chromium`, which may still fail.

**Current mitigation:** doctor.mjs has a try/catch, tells user to run install command. Acceptable.

**Improvement:** Add more specific error message for Linux (list missing deps).

### 2. Node.js 18+ Requirement Not Enforced at Runtime

**Issue:** `doctor.mjs` checks Node version >= 18, but scripts don't enforce it. User could run scripts on Node 16 and get cryptic errors.

**Files:** `doctor.mjs` (line 23), no enforcement in package.json.

**Risk:** Low (most modern installs are 18+), but edge case for old Macs/WSL setups.

**Fix approach:** Add `.engines.node` to package.json: `"engines": { "node": ">=18" }` and `npm install --save` will warn on downgrade.

## Webhooks & Async Concerns

### 1. No Persistence Between Script Runs

**Issue:** Each script (merge, dedup, verify) is stateless — no transaction log, no undo, no recovery from partial failure.

**Files:** All utility scripts use simple read → modify → write.

**Scenario:** During merge-tracker.mjs, user's computer crashes after writing 30 of 79 TSVs to merged/. No way to know which files were processed.

**Current mitigation:** Backup is created before write (normalize-statuses.mjs, dedup-tracker.mjs). Not comprehensive.

**Improvement:** Log each operation with timestamp, commit hash, status to `.log/operations.jsonl` for auditability.

---

## Summary Table

| Category | Count | Severity |
|----------|-------|----------|
| Tech Debt | 3 | Medium |
| Known Bugs | 3 | Low |
| Security | 2 | Low |
| Performance | 2 | Low |
| Fragile Areas | 3 | Medium |
| Test Gaps | 2 | Medium |
| Missing Features | 2 | Low |
| Scaling Limits | 2 | Low |
| Dependencies | 2 | Low |
| **TOTAL** | **21** | **Mostly Low-Medium** |

## Recommendations (Priority Order)

**High Priority (fixes blocking workflows):**
1. Implement interview-prep mode fully (user-facing gap)
2. Add batch processing end-to-end test
3. Fix merge-tracker column detection heuristic

**Medium Priority (stability & maintainability):**
4. Standardize applications.md location (data/ only)
5. Load states.yml instead of hardcoding
6. Add Playwright page recovery in check-liveness.mjs
7. Fix scan.mjs URL canonicalization

**Low Priority (nice-to-have):**
8. Add rate limiting to scan.mjs
9. Bulk update tool for applications.md
10. Report template generator

---

*Concerns audit: 2026-04-14*
