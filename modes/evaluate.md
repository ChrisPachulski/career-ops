# Mode: evaluate -- Full Evaluation A-G

When the candidate pastes an offer (text or URL), ALWAYS deliver all 7 blocks (A-F evaluation + G legitimacy):

## Step 0 -- Context Loading

**If `career-ops-brain.md` exists in the project root**, read it INSTEAD of loading cv.md + _shared.md + _profile.md + profile.yml separately. The brain contains all necessary context (candidate profile, scoring rules, archetypes, evaluation format) in condensed form (~3.3K tokens vs ~12K tokens from separate files). This is the preferred path for batch and pipeline evaluations.

**If brain.md does not exist**, fall back to reading the individual files as listed in _shared.md "Sources of Truth."

## Step 0b -- Archetype Detection

Classify the offer into one of the 6 archetypes (see `_shared.md` or brain.md Section 3). If it is a hybrid, indicate the 2 closest matches. This determines:
- Which proof points to prioritize in Block B
- How to rewrite the summary in Block E
- Which STAR stories to prepare in Block F

## Block A -- Role Summary

Table with:
- Detected archetype
- Domain (platform/agentic/LLMOps/ML/enterprise)
- Function (build/consult/manage/deploy)
- Seniority
- Remote (full/hybrid/onsite)
- Team size (if mentioned)
- TL;DR in 1 sentence

## Block B -- CV Match

Read `cv.md`. Create a table mapping each JD requirement to exact lines in the CV.

**Adapted to archetype:**
- If FDE -> prioritize proof points for fast delivery and client-facing work
- If SA -> prioritize system design and integrations
- If PM -> prioritize product discovery and metrics
- If LLMOps -> prioritize evals, observability, pipelines
- If Agentic -> prioritize multi-agent, HITL, orchestration
- If Transformation -> prioritize change management, adoption, scaling

**Gaps** section with a mitigation strategy for each one. For each gap:
1. Is it a hard blocker or a nice-to-have?
2. Can the candidate demonstrate adjacent experience?
3. Is there a portfolio project that covers this gap?
4. Concrete mitigation plan (phrase for cover letter, quick project, etc.)

## Block C -- Level and Strategy

1. **Level detected** in the JD vs **candidate's natural level for that archetype**
2. **"Sell senior without lying" plan**: specific phrases adapted to the archetype, concrete achievements to highlight, how to position founder experience as an advantage
3. **"If they downlevel me" plan**: accept if comp is fair, negotiate a review at 6 months, clear promotion criteria

## Block D -- Comp and Demand

**Company comp cache (check BEFORE WebSearch):**
1. Read `wiki/career-ops/career-ops-company-intelligence.md` (if exists)
2. If the company has a comp range entry updated within the last 30 days, use it and cite "career-ops company intelligence, verified {date}"
3. If the JD posts a salary range, use that as primary source
4. **Only use WebSearch** if: (a) company is not in the wiki, (b) wiki data is >30 days old, or (c) you need to verify/update a stale entry
5. When WebSearch IS used, update the wiki comp range for future evaluations

WebSearch targets (when needed):
- Current salaries for the role (Glassdoor, Levels.fyi, Blind)
- Company compensation reputation
- Role demand trends

Table with data and cited sources. If no data is available, say so instead of making things up.

## Block E -- Customization Plan

| # | Section | Current State | Proposed Change | Why |
|---|---------|---------------|-----------------|-----|
| 1 | Summary | ... | ... | ... |
| ... | ... | ... | ... | ... |

Top 5 CV changes + Top 5 LinkedIn changes to maximize match.

## Block F -- Interview Plan

6-10 STAR+R stories mapped to JD requirements (STAR + **Reflection**):

| # | JD Requirement | STAR+R Story | S | T | A | R | Reflection |
|---|----------------|--------------|---|---|---|---|------------|

The **Reflection** column captures what was learned or what would be done differently. This signals seniority -- junior candidates describe what happened, senior candidates extract lessons.

**Story Bank:** Write STAR+R stories to `interview-prep/story-bank.md` under `## {YYYY-MM-DD} -- {company}` with subheadings `## S:` / `## T:` / `## A:` / `## R:` / `## Reflection:`. Then run:

```bash
node scripts/db-write.mjs insert-story --file interview-prep/story-bank.md
```

The ingester reads the file and upserts each story into the `star_stories` table. Over time this builds a reusable bank of 5-10 master stories that can be adapted to any interview question.

**Selected and framed according to archetype:**
- FDE -> emphasize delivery speed and client-facing work
- SA -> emphasize architecture decisions
- PM -> emphasize discovery and trade-offs
- LLMOps -> emphasize metrics, evals, production hardening
- Agentic -> emphasize orchestration, error handling, HITL
- Transformation -> emphasize adoption, organizational change

Also include:
- 1 recommended case study (which project to present and how)
- Red-flag questions and how to answer them (e.g., "Why did you sell your company?", "Do you have direct reports?")

## Block G -- Posting Legitimacy

Analyze the job posting for signals that indicate whether this is a real, active opening. This helps the user prioritize their effort on opportunities most likely to result in a hiring process.

**Ethical framing:** Present observations, not accusations. Every signal has legitimate explanations. The user decides how to weigh them.

### Signals to analyze (in order):

**1. Posting Freshness** (from Playwright snapshot, already captured in Step 0):
- Date posted or "X days ago" -- extract from page
- Apply button state (active / closed / missing / redirects to generic page)
- If URL redirected to generic careers page, note it

**2. Description Quality** (from JD text):
- Does it name specific technologies, frameworks, tools?
- Does it mention team size, reporting structure, or org context?
- Are requirements realistic? (years of experience vs technology age)
- Is there a clear scope for the first 6-12 months?
- Is salary/compensation mentioned?
- What ratio of the JD is role-specific vs generic boilerplate?
- Any internal contradictions? (entry-level title + staff requirements, etc.)

**3. Company Hiring Signals** (2-3 WebSearch queries, combine with Block D research):
- Search: `"{company}" layoffs {year}` -- note date, scale, departments
- Search: `"{company}" hiring freeze {year}` -- note any announcements
- If layoffs found: are they in the same department as this role?

**4. Reposting Detection** (from scan-history.tsv):
- Check if company + similar role title appeared before with a different URL
- Note how many times and over what period

**5. Role Market Context** (qualitative, no additional queries):
- Is this a common role that typically fills in 4-6 weeks?
- Does the role make sense for this company's business?
- Is the seniority level one that legitimately takes longer to fill?

### Output format:

**Assessment:** One of three tiers:
- **High Confidence** -- Multiple signals suggest a real, active opening
- **Proceed with Caution** -- Mixed signals worth noting
- **Suspicious** -- Multiple ghost job indicators, investigate before investing time

**Signals table:** Each signal observed with its finding and weight (Positive / Neutral / Concerning).

**Context Notes:** Any caveats (niche role, government job, evergreen position, etc.) that explain potentially concerning signals.

### Edge case handling:
- **Government/academic postings:** Longer timelines are standard. Adjust thresholds (60-90 days is normal).
- **Evergreen/continuous hire postings:** If the JD explicitly says "ongoing" or "rolling," note it as context -- this is not a ghost job, it is a pipeline role.
- **Niche/executive roles:** Staff+, VP, Director, or highly specialized roles legitimately stay open for months. Adjust age thresholds accordingly.
- **Startup / pre-revenue:** Early-stage companies may have vague JDs because the role is genuinely undefined. Weight description vagueness less heavily.
- **No date available:** If posting age cannot be determined and no other signals are concerning, default to "Proceed with Caution" with a note that limited data was available. NEVER default to "Suspicious" without evidence.
- **Recruiter-sourced (no public posting):** Freshness signals unavailable. Note that active recruiter contact is itself a positive legitimacy signal.

---

## Scoring

After completing blocks A-F, extract JD features into the `JDFeatures` schema and run the scoring engine. See `modes/_shared.md` "Scoring System" section for the extraction and invocation workflow. The engine output includes the score table and interpretation -- use them directly in the report.

---

## Post-evaluation

**ALWAYS** after generating blocks A-G:

### 1. Save report .md and register it

Save the full evaluation to `reports/{###}-{company-slug}-{YYYY-MM-DD}.md`, THEN immediately register it in DuckDB:

```bash
node scripts/db-write.mjs insert-report --file reports/{###}-{company-slug}-{YYYY-MM-DD}.md
```

- `{###}` = next sequential number (3 digits, zero-padded)
- `{company-slug}` = company name in lowercase, no spaces (use hyphens)
- `{YYYY-MM-DD}` = current date

The ingester parses the report header (URL, Score, Legitimacy, Archetype, TL;DR, Remote, Comp, Batch ID), inserts the `reports` row with the full markdown in `body`, UPSERTs the corresponding `applications` row, and refreshes `data/dashboard.json`. **Do not manually edit `data/applications.md`** -- it is regenerated from DuckDB.

**Report format:**

```markdown
# Evaluation: {Company} -- {Role}

**Date:** {YYYY-MM-DD}
**Archetype:** {detected}
**Score:** {X/5}
**Legitimacy:** {High Confidence | Proceed with Caution | Suspicious}
**PDF:** {path or pending}

---

## A) Role Summary
(full content of Block A)

## B) CV Match
(full content of Block B)

## C) Level and Strategy
(full content of Block C)

## D) Comp and Demand
(full content of Block D)

## E) Customization Plan
(full content of Block E)

## F) Interview Plan
(full content of Block F)

## G) Posting Legitimacy
(full content of Block G)

## H) Draft Application Answers
(only if score >= 4.5 -- draft answers for the application form)

---

## Extracted Keywords
(list of 15-20 keywords from the JD for ATS optimization)
```

### 2. Tracker row (auto-created)

The tracker row in `applications` is created by the ingester in step 1 from the report header fields. **Do not write to `data/applications.md`** -- it is a regenerated markdown view of `data/career-ops.duckdb`. The view refreshes automatically on next render; force a refresh any time with:

```bash
node scripts/db-write.mjs render-markdown applications
```
