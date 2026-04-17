# Mode: recompile -- Brain Compilation

Reads all source files + wiki intelligence and produces a single condensed document (`career-ops-brain.md`) that evaluation agents use instead of reading 5 separate files.

## When to Run

- After initial setup
- When `/career-ops pipeline` reports dimension drift >0.5
- After major CV updates
- After changing comp targets or archetypes
- Manually via `/career-ops recompile`

## Workflow

### Step 1 -- Read Source Files

Read these files from the project root:

1. `cv.md`
2. `config/profile.yml`
3. `modes/_profile.md`
4. `modes/_shared.md`
5. `modes/evaluate.md`
6. `article-digest.md` (if exists)

### Step 2 -- Read Wiki Intelligence

Read these files if they exist (skip silently if missing):

1. `wiki/career-ops/career-ops-evaluation-intelligence.md`
2. `wiki/career-ops/career-ops-company-intelligence.md`
3. `wiki/career-ops/career-ops-scan-intelligence.md`

### Step 3 -- Compile career-ops-brain.md

Build the brain document with these sections. All sections are condensed. Total target is ~3,300 tokens (~13,200 chars).

**Section 1: Candidate Identity (~200 tokens)**
- Extract: name, email, location, timezone, visa status, comp targets (target + minimum), location scoring rules (4 lines max)
- Source: `config/profile.yml` + `modes/_profile.md` "Your Location Policy"

**Section 2: Proof Points (~500 tokens)**
- Extract: condensed metrics table only -- columns: project name | hero metric | archetype relevance
- Source: `cv.md` Experience section + `article-digest.md` (if exists, takes precedence per data contract)
- NOT full job descriptions, NOT responsibilities -- just quantified achievements

**Section 3: Archetypes + Framing (~400 tokens)**
- Extract: 6-row archetype table (archetype | what they buy | key proof points)
- Source: `modes/_profile.md` "Your Target Roles" + "Adaptive Framing"
- Include exit narrative (one paragraph)

**Section 4: Scoring Rules (~600 tokens)**
- Extract: 6 dimensions with weights, blocker gate criteria (5 types + severity thresholds), score interpretation (4 bands)
- Source: `modes/_shared.md` "Scoring System" section
- Condense to essential rules only -- no examples or elaboration

**Section 5: Evaluation Format (~800 tokens)**
- Extract: Block A-G one-paragraph descriptions, report filename convention (`{###}-{slug}-{YYYY-MM-DD}.md`), tracker TSV format (9 tab-separated columns)
- Source: `modes/evaluate.md`
- One paragraph per block, not full templates

**Section 6: Current Intelligence (~500 tokens)**
- Extract: company status table (active/frozen/stale), calibration baselines, top 3 failure modes
- Source: wiki articles (if they exist; if not, leave section with "Run evaluations to populate")
- Include dimension mean baselines from `data/baselines.yml`

**Section 7: JD Armor (~300 tokens)**
- Extract: 5-layer detection summary (hidden text, prompt injection, invisible requirements, form traps, output sanitization) -- one line per layer with key patterns
- Source: `modes/_shared.md` "JD Armor" section

### Step 4 -- Write the Brain

Write the compiled brain to `career-ops-brain.md` in the project root.

Include this header:

```
# Career-Ops Brain v{N}
Compiled: {YYYY-MM-DD} | Source hash: {first 8 chars of combined file hash}
```

Where `{N}` is the next sequential version number (read previous brain to get current version, or start at v1).

Compute the source hash by concatenating the contents of all source files read in Steps 1-2 and taking the first 8 characters of the SHA-256 hex digest.

### Step 5 -- Snapshot Baselines

Write baselines to `data/baselines.yml`:

1. Read all reports in `reports/` directory
2. Parse scores from report headers (`Score: X/5`)
3. Compute dimension means (if available in reports) or global score mean
4. Compute failure rates by type: expired, location, downlevel, comp, domain, management
5. Write YAML with these fields:

```yaml
compiled_date: YYYY-MM-DD
eval_count: {number of reports parsed}
score_mean: {weighted average}
dimension_means:
  cv_match: {mean}
  archetype_fit: {mean}
  comp_alignment: {mean}
  level_fit: {mean}
  org_risk: {mean}
  blockers: {mean}
failure_rates:
  expired: {rate}
  location: {rate}
  downlevel: {rate}
  comp: {rate}
  domain: {rate}
  management: {rate}
```

### Step 6 -- Output Summary

Print a summary with:

- Brain size (chars and estimated tokens at ~4 chars/token)
- Sections compiled with source verification (which source files were read for each section)
- Baselines snapshot (eval count, score mean)
- Final line: "Brain ready. Evaluation agents will read career-ops-brain.md instead of 5 separate files."

## Quality Rules

- Total brain size MUST be under 16K chars (~4K tokens). If it exceeds this, condense further.
- Never include full job descriptions, full STAR stories, or negotiation scripts in the brain.
- Proof points are METRICS ONLY (numbers, not narratives).
- Scoring rules are RULES ONLY (weights, thresholds, not examples or calibration benchmarks).
- The brain is a reference card, not a manual.

## Brain Versioning

- Version number = sequential integer (v1, v2, v3...)
- Each recompile increments the version
- Previous brain is NOT backed up (source files are the backup)
