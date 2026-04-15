# Scoring Engine Design

**Date:** 2026-04-14
**Status:** Approved
**Location:** `scoring/` directory in career-ops repo

## Problem

The career-ops evaluation system claims a 6-dimension weighted scoring engine, but all scoring logic lives as prose instructions in `modes/_shared.md`. Claude interprets these instructions on the fly, producing non-reproducible scores -- same JD on different days yields different numbers. There are no tests, no audits, and no way to answer "why did this score 3.8?"

## Solution

A deterministic Python scoring engine. Claude extracts structured features from JDs into a Pydantic schema. Python computes all scores from that schema. Same input always produces the same output.

## Architecture

```
Claude reads JD
    |
    v
Extracts structured features -> JDFeatures (Pydantic model)
    |
    v
Python scoring engine (pure functions, no I/O)
    |
    v
ScoreResult (dimensions, global score, blocker gate, markdown table)
    |
    v
Claude uses ScoreResult in evaluation report
```

## Input Schema

### JDFeatures

```python
class Requirement(BaseModel):
    text: str                              # the JD requirement as written
    priority: Literal["must", "preferred", "nice"]
    match_strength: float                  # 0.0-1.0, Claude's assessment
    evidence: str                          # proof point from CV/experience

class OrgSignals(BaseModel):
    glassdoor_rating: float | None         # 1.0-5.0 scale, None if unavailable
    recent_layoffs: bool | None            # True if layoffs in last 12 months
    org_stability: float                   # 1.0-5.0, Claude's assessment
    remote_policy: Literal["remote", "hybrid", "onsite", "unknown"]
    location_fit: float                    # 1.0-5.0, how well location works

class Blocker(BaseModel):
    type: Literal["credentials", "citizenship", "experience_years", "domain", "geographic"]
    description: str
    severity: float                        # 1.0 (absolute barrier) to 2.0 (very difficult)

class JDFeatures(BaseModel):
    # Comp Alignment inputs
    salary_low: float | None
    salary_high: float | None
    salary_midpoint: float | None          # inferred if range not posted
    comp_target: float                     # user's target from profile.yml

    # Level Fit inputs
    jd_seniority: Literal["junior", "mid", "senior", "staff", "principal", "director", "vp"]
    candidate_seniority: Literal["junior", "mid", "senior", "staff", "principal", "director", "vp"]

    # Archetype Fit inputs
    detected_archetype: str
    target_archetypes: list[str]           # from _profile.md
    archetype_adjacency: float             # 0.0-1.0, Claude's adjacency assessment

    # CV Match inputs
    requirements: list[Requirement]

    # Org Risk inputs
    org_signals: OrgSignals

    # Blockers
    blockers: list[Blocker]
```

## Scoring Functions

All functions are pure -- no file I/O, no side effects, no randomness.

### score_comp_alignment

```
Input: salary_low, salary_high, comp_target
Logic:
  - If no salary info (all None): 3.0 (neutral, no signal)
  - Compute effective salary = midpoint of range, or midpoint if given, or whichever bound exists
  - ratio = effective_salary / comp_target
  - ratio >= 1.0:         5.0
  - 0.86 <= ratio < 1.0:  4.0  (1-14% below)
  - 0.71 <= ratio < 0.86: 3.0  (15-29% below)
  - ratio < 0.71:         2.0  (30%+ below)
Output: float (1.0-5.0)
```

### score_level_fit

```
Input: jd_seniority, candidate_seniority
Logic:
  - Define level order: junior=0, mid=1, senior=2, staff=3, principal=4, director=5, vp=6
  - delta = jd_level - candidate_level
  - delta == 0:   5.0  (exact match)
  - delta == 1:   4.0  (one up, stretch)
  - delta == -1:  3.0  (one down)
  - abs(delta) >= 2: 2.0
Output: float (1.0-5.0)
```

### score_archetype_fit

```
Input: detected_archetype, target_archetypes, archetype_adjacency
Logic:
  - If detected_archetype in target_archetypes: 5.0 (exact match)
  - If adjacency >= 0.6: 3.0 + (adjacency * 2.0), capped at 4.5
  - If adjacency < 0.3: 1.0 + (adjacency * 5.0)
  - Otherwise (0.3 <= adjacency < 0.6): 2.5 + (adjacency * 2.5)
Output: float (1.0-5.0)
```

### score_cv_match

```
Input: requirements (list of Requirement)
Logic:
  - Weight multipliers: must=3, preferred=2, nice=1
  - weighted_sum = sum(r.match_strength * weight[r.priority] for r in requirements)
  - total_weight = sum(weight[r.priority] for r in requirements)
  - raw = weighted_sum / total_weight  (0.0-1.0)
  - Scale to 1.0-5.0: score = 1.0 + (raw * 4.0)
  - If no requirements: 3.0 (neutral)
Output: float (1.0-5.0)
```

### score_org_risk

```
Input: org_signals (OrgSignals)
Logic:
  - Collect scored signals into a list:
    - glassdoor: if available, scale from 1-5 Glassdoor to 1.0-5.0 directly. If None, skip.
    - recent_layoffs: True=2.0, False=5.0, None=skip
    - org_stability: pass through (already 1.0-5.0)
    - remote_policy: remote=5.0, hybrid=4.0, onsite=2.5, unknown=3.0
    - location_fit: pass through (already 1.0-5.0)
  - score = mean of all non-skipped signals
  - If no signals: 3.0 (neutral)
Output: float (1.0-5.0)
```

### score_blockers

```
Input: blockers (list of Blocker)
Logic:
  - If empty: 5.0 (no blockers)
  - Otherwise: min(b.severity for b in blockers)  (returns 1.0-2.0)
Output: float (1.0-5.0)
```

### compute_global

```
Input: all 6 dimension scores
Logic:
  - weights = {cv_match: 0.25, archetype_fit: 0.20, comp_alignment: 0.20,
               level_fit: 0.15, org_risk: 0.10, blockers: 0.10}
  - weighted_sum = sum(score * weight for each dimension)
  - If any blockers exist: cap at min(weighted_sum, 2.5)
  - Truncate to one decimal place (floor, never round up to cross thresholds)
Output: float (1.0-5.0)
```

## Output Schema

### ScoreResult

```python
class DimensionScore(BaseModel):
    name: str
    score: float
    weight: float
    weighted: float
    reasoning: str                         # one-line explanation of why this score

class ScoreResult(BaseModel):
    dimensions: list[DimensionScore]
    global_score: float
    blocker_gate_active: bool
    blocker_gate_reason: str | None
    interpretation: str                    # "Strong match", "Good match", etc.
    score_table: str                       # pre-formatted markdown table for reports
```

### Interpretation Thresholds

```
4.5+:      "Strong match -- recommend applying immediately"
4.0-4.4:   "Good match -- worth applying"
3.5-3.9:   "Decent but not ideal -- apply only with specific reason"
Below 3.5: "Below threshold -- recommend against applying"
```

## File Layout

```
scoring/
    __init__.py
    models.py          # Pydantic schemas (JDFeatures, ScoreResult, Requirement, etc.)
    engine.py          # Pure scoring functions + compute_global
    calibrate.py       # Back-test against 58 existing reports
    cli.py             # CLI entry point: python -m scoring.cli --input features.json
```

### cli.py behavior

```
python -m scoring.cli --input features.json
  -> reads JDFeatures from JSON
  -> validates with Pydantic
  -> runs engine
  -> writes ScoreResult to stdout as JSON
  -> exits 0 on success, 1 on validation error
```

### calibrate.py behavior

```
python -m scoring.calibrate --reports-dir reports/
  -> reads each report markdown
  -> extracts original dimension scores and global score from the score table
  -> extracts features (salary, level, archetype, etc.) from report narrative
  -> runs engine on extracted features
  -> outputs comparison table: original score vs engine score per dimension per report
  -> flags divergences > 0.5 as significant
```

## Integration with Modes

Update `modes/evaluate.md` and `modes/_shared.md`:

1. After Claude extracts JD content and performs analysis (blocks A-F), it fills a `JDFeatures` JSON
2. Claude writes the JSON to a temp file
3. Claude runs `python scoring/cli.py --input /tmp/features.json`
4. Claude reads the `ScoreResult` JSON from stdout
5. Claude uses the `score_table` field directly in the report
6. Claude uses `interpretation` for the recommendation

The scoring rules prose in `_shared.md` gets replaced with: "Run the scoring engine. Use the output. Do not compute scores manually."

## What Stays with Claude

- Reading and interpreting JDs (feature extraction into schema)
- Assessing `match_strength` for each requirement (0.0-1.0)
- Classifying archetype and assessing adjacency (0.0-1.0)
- Assessing org stability (1.0-5.0)
- Writing evaluation report narrative
- All non-scoring modes (scan, pipeline, apply, contact, pdf, etc.)

## What Moves to Python

- All score computation (6 dimensions + global)
- Blocker gate logic and enforcement
- Score interpretation thresholds
- Weighted sum calculation with truncation
- Score table formatting
- Calibration and back-testing

## Back-Testing Plan

After the engine is built, `calibrate.py` runs against all 58 reports in `reports/`:

1. Parse each report's score table (regex on markdown table)
2. Extract whatever features are available from the report narrative
3. For features that can't be extracted (e.g., match_strength per requirement), use the original dimension score as a proxy
4. Run engine, compare global scores
5. Output: CSV with columns (report, original_global, engine_global, delta, largest_dimension_divergence)
6. Summary statistics: mean absolute deviation, max divergence, correlation

This reveals where Claude's prose-based scoring was inconsistent with the deterministic rules it was supposed to follow.

## Dependencies

- Python 3.12
- pydantic (validation)
- No other external dependencies for the engine itself
- calibrate.py may use pandas for the comparison table (already available in the environment)

## Testing

- Unit tests for each scoring function with edge cases
- Integration test: full JDFeatures -> ScoreResult pipeline
- Calibration test: verify engine produces expected scores for the 9 calibration benchmarks from _shared.md
- Blocker gate test: verify cap at 2.5 regardless of other dimensions
