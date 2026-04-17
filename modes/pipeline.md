# Mode: pipeline — URL Inbox (Second Brain)

Processes offer URLs accumulated in `data/pipeline.md`. The user adds URLs whenever they want and then runs `/career-ops pipeline` to process them all.

## Workflow

1. **Read** `data/pipeline.md` — look for `- [ ]` items in the "Pending" section
2. **Pre-flight screening + JD extraction (inline, no agents)**:
   Screen each URL and extract JD content in a single WebFetch. This eliminates dead/mismatched postings AND caches the JD text so evaluation agents never re-fetch it.

   a. **Company intelligence check**: Read `wiki/career-ops/career-ops-company-intelligence.md` (if exists). If company status is "FROZEN" or "all_expired", skip without touching the URL — mark `- [!] {url} | {company} | {title} — SKIPPED: company frozen/stale per wiki` and continue.

   b. **Combined liveness + JD extraction**: WebFetch the URL with this prompt:
      ```
      Extract from this job posting page:
      STATUS: LIVE or DEAD (DEAD if: error page, "no longer available", "position filled", redirect to generic careers, or content < 300 chars)
      LOCATION: [city, state/country or "Remote" or "Remote US"]
      LEVEL: [junior/mid/senior/staff/principal/director/vp]
      COMP: [salary range if posted, or UNKNOWN]
      TITLE: [exact job title from page]
      REQS: [top 5 requirements, pipe-separated, one phrase each]
      JD_TEXT: [full job description text, preserve all details]
      ```
      Cost: ~300-500 tokens for extraction. Replaces both the pre-flight check AND the agent's JD fetch.

      **Platform-specific URL handling:**
      - **Greenhouse HTML** (`job-boards.greenhouse.io`): may redirect (302). Follow the redirect URL and re-fetch. Alternatively, use the API: replace `job-boards.greenhouse.io/{company}/jobs/{id}` with `boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}` for structured JSON.
      - **Ashby** (`jobs.ashbyhq.com`): JavaScript SPA -- WebFetch returns empty/minimal content. Use Playwright if available; otherwise, try the Ashby API: `https://jobs.ashbyhq.com/api/non-user-graphql` with POST body `{"operationName":"apiJobPosting","variables":{"organizationHostedJobsPageName":"{company}","jobPostingId":"{uuid}"}}`. If neither works, mark `- [?] {url} | NEEDS_PLAYWRIGHT` and batch these for manual/Playwright processing later.
      - **Coinbase, LinkedIn, or other 403 sites**: WebFetch blocked. Mark `- [?] {url} | NEEDS_PLAYWRIGHT` and batch for Playwright. Do NOT skip -- these may be live high-value roles.
      - **Lever** (`jobs.lever.co`): Usually works with WebFetch. If 404, posting is closed.

   c. **If STATUS = DEAD**: mark `- [!]` with note and continue.

   d. **Location filter**: Check LOCATION against `portals.yml` `location_filter`. If reject keyword matches and no accept keyword present, skip — mark `- [!] {url} | SKIPPED: {location} outside acceptable geography`.

   e. **Passed pre-flight**: URL is live and location-acceptable. Store the extracted JD_TEXT, LEVEL, COMP, REQS for use in Tier 1 screening.

3. **Tier 1: Quick screen (inline, no agents)**:
   For each URL that passed pre-flight, the orchestrator does an inline score estimate using brain.md rules and the extracted JD metadata. No agent spawn, no WebSearch, no report generation.

   Using the extracted LEVEL, COMP, LOCATION, REQS, and TITLE:
   a. **Archetype detection**: Match TITLE + REQS against brain.md Section 3 archetypes. Score: exact match = 5.0, adjacent = 3.5, wrong function = 2.0.
   b. **Level check**: Compare LEVEL to candidate's natural level (Staff). Same = 5.0, one up = 4.0, one down = 3.0, two+ = 2.0.
   c. **Comp check**: If COMP is known, compare to $250K target. At/above = 5.0, 1-14% below = 4.0, 15-29% = 3.0, 30%+ = 2.0. If UNKNOWN, use company intelligence wiki or default 3.0.
   d. **Location check**: Apply brain.md Section 1 location scoring (already extracted).
   e. **Quick blocker scan**: Check REQS for hard blockers (management requirement, specific credentials, domain lock-in). If hard blocker found, cap at 2.5.
   f. **Estimate**: Weighted average using brain.md Section 4 weights. No CV Match dimension at this tier (that requires reading the full JD).

   **Tier 1 verdict**:
   - Estimated 3.8+ (likely actionable): Promote to **Tier 2** (spawn evaluation agent)
   - Estimated 3.0-3.7 (borderline): Record as Tier 1 result. Write brief tracker entry (status: "Screened-T1", note includes estimated score and one-line reason). No report file. Mark `- [x] T1 | {url} | {company} | {title} | ~{score}/5 | SKIP`
   - Estimated below 3.0 (clear miss): Same as above but with stronger skip recommendation.

   **Tier 1 does NOT produce**: Full reports, STAR stories, customization plans, comp research, interview prep. These are Tier 2 only.

4. **Tier 2: Full evaluation (agents, only for estimated 3.8+)**:
   For each URL promoted from Tier 1:
   a. Calculate next sequential `REPORT_NUM`
   b. Spawn evaluation agent with:
      - `career-ops-brain.md` as context (~2.1K tokens)
      - The pre-extracted JD_TEXT from step 2 (passed directly in agent prompt -- agent does NOT re-fetch the URL)
      - Company comp data from wiki (if available and < 30 days old -- agent skips WebSearch for that company)
   c. Agent runs full A-G evaluation, writes report + tracker TSV
   d. Mark `- [x] #NNN | {url} | {company} | {title} | {score}/5 | PDF`
5. **If there are 3+ Tier 2 URLs**, launch parallel agents to maximize speed.

6. **Post-batch threshold check**:
   After completing all evaluations in a batch:
   a. Read `data/baselines.yml` for compiled baselines
   b. Compute running dimension means from new evaluations (Tier 2 results only)
   c. Compare each dimension to baseline
   d. If any dimension mean shifted >0.5: print `DRIFT DETECTED: {dimension} shifted from {baseline} to {current}. Recommend running /career-ops recompile.`
   e. If expired rate or location reject rate shifted >0.15 from baseline: recommend updating portals.yml or location_filter
   f. Update wiki articles with new data (append to career-ops-evaluation-intelligence.md and career-ops-company-intelligence.md)

7. **When finished**, display a summary table:

```
| # | Company | Role | Score | PDF | Recommended Action |
```

## pipeline.md Format

```markdown
## Pending
- [ ] https://jobs.example.com/posting/123
- [ ] https://boards.greenhouse.io/company/jobs/456 | Company Inc | Senior PM
- [!] https://private.url/job — Error: login required

## Processed
- [x] #143 | https://jobs.example.com/posting/789 | Acme Corp | AI PM | 4.2/5 | PDF ✅
- [x] #144 | https://boards.greenhouse.io/xyz/jobs/012 | BigCo | SA | 2.1/5 | PDF ❌
```

## Smart JD Detection from URL

1. **Playwright (preferred):** `browser_navigate` + `browser_snapshot`. Works with all SPAs.
2. **WebFetch (fallback):** For static pages or when Playwright is not available.
3. **WebSearch (last resort):** Search secondary portals that index the JD.

**Special cases:**
- **LinkedIn**: May require login — mark `[!]` and ask the user to paste the text
- **PDF**: If the URL points to a PDF, read it directly with the Read tool
- **`local:` prefix**: Read the local file. Example: `local:jds/linkedin-pm-ai.md` — read `jds/linkedin-pm-ai.md`

## Automatic Numbering

1. List all files in `reports/`
2. Extract the number from the prefix (e.g., `142-medispend...` — 142)
3. New number = highest found + 1

## Source Synchronization

Before processing any URL, verify sync:
```bash
node cv-sync-check.mjs
```
If there is a desynchronization, warn the user before continuing.
