# Scoring Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic Python scoring engine that replaces prose-based scoring in career-ops. Claude extracts structured features from JDs, Python computes all scores.

**Architecture:** Pydantic models define the input/output contract. Pure functions compute each of the 6 dimension scores independently, then `compute_global` combines them with weights and applies the blocker gate. CLI reads JSON from stdin/file, writes ScoreResult JSON to stdout.

**Tech Stack:** Python 3.12, Pydantic 2.x, pytest 9.x. No other dependencies for the engine. pandas for calibrate.py (already available).

**Spec:** `docs/superpowers/specs/2026-04-14-scoring-engine-design.md`

---

## File Map

| File | Purpose |
|------|---------|
| Create: `scoring/__init__.py` | Package marker, exports `score` convenience function |
| Create: `scoring/models.py` | Pydantic schemas: JDFeatures, ScoreResult, sub-models |
| Create: `scoring/engine.py` | 6 scoring functions + compute_global, all pure |
| Create: `scoring/cli.py` | CLI entry point: JSON in -> ScoreResult JSON out |
| Create: `scoring/calibrate.py` | Back-test engine against 67 existing reports |
| Create: `tests/test_models.py` | Schema validation tests |
| Create: `tests/test_engine.py` | Unit tests for all scoring functions |
| Create: `tests/test_cli.py` | CLI integration tests |
| Modify: `modes/_shared.md` | Replace scoring prose with engine invocation |
| Modify: `modes/evaluate.md` | Add feature extraction schema instructions |

---

### Task 1: Scaffold + Pydantic Models

**Files:**
- Create: `scoring/__init__.py`
- Create: `scoring/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p scoring tests
```

- [ ] **Step 2: Write failing tests for model validation**

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError

from scoring.models import (
    Requirement,
    OrgSignals,
    Blocker,
    JDFeatures,
    DimensionScore,
    ScoreResult,
)


# --- Requirement ---

def test_requirement_valid():
    r = Requirement(
        text="5+ years Python",
        priority="must",
        match_strength=0.9,
        evidence="7 years Python at WotC and NCC",
    )
    assert r.priority == "must"
    assert r.match_strength == 0.9


def test_requirement_rejects_invalid_priority():
    with pytest.raises(ValidationError):
        Requirement(
            text="5+ years Python",
            priority="critical",
            match_strength=0.9,
            evidence="7 years",
        )


def test_requirement_rejects_match_strength_out_of_range():
    with pytest.raises(ValidationError):
        Requirement(
            text="5+ years Python",
            priority="must",
            match_strength=1.5,
            evidence="7 years",
        )


def test_requirement_rejects_negative_match_strength():
    with pytest.raises(ValidationError):
        Requirement(
            text="5+ years Python",
            priority="must",
            match_strength=-0.1,
            evidence="7 years",
        )


# --- OrgSignals ---

def test_org_signals_valid_full():
    s = OrgSignals(
        glassdoor_rating=4.2,
        recent_layoffs=False,
        org_stability=4.0,
        remote_policy="remote",
        location_fit=5.0,
    )
    assert s.glassdoor_rating == 4.2


def test_org_signals_valid_minimal():
    s = OrgSignals(
        glassdoor_rating=None,
        recent_layoffs=None,
        org_stability=3.0,
        remote_policy="unknown",
        location_fit=3.0,
    )
    assert s.glassdoor_rating is None


def test_org_signals_rejects_bad_remote_policy():
    with pytest.raises(ValidationError):
        OrgSignals(
            glassdoor_rating=None,
            recent_layoffs=None,
            org_stability=3.0,
            remote_policy="flexible",
            location_fit=3.0,
        )


# --- Blocker ---

def test_blocker_valid():
    b = Blocker(
        type="citizenship",
        description="Requires US citizenship",
        severity=1.0,
    )
    assert b.type == "citizenship"


def test_blocker_rejects_severity_out_of_range():
    with pytest.raises(ValidationError):
        Blocker(type="citizenship", description="test", severity=3.0)


def test_blocker_rejects_severity_below_minimum():
    with pytest.raises(ValidationError):
        Blocker(type="citizenship", description="test", severity=0.5)


def test_blocker_rejects_invalid_type():
    with pytest.raises(ValidationError):
        Blocker(type="salary", description="test", severity=1.5)


# --- JDFeatures ---

def test_jd_features_minimal():
    f = JDFeatures(
        salary_low=None,
        salary_high=None,
        salary_midpoint=None,
        comp_target=250000,
        jd_seniority="staff",
        candidate_seniority="staff",
        detected_archetype="AI Platform/LLMOps",
        target_archetypes=["AI Platform/LLMOps", "Agentic/Automation"],
        archetype_adjacency=1.0,
        requirements=[],
        org_signals=OrgSignals(
            glassdoor_rating=None,
            recent_layoffs=None,
            org_stability=3.0,
            remote_policy="unknown",
            location_fit=3.0,
        ),
        blockers=[],
    )
    assert f.comp_target == 250000


def test_jd_features_rejects_invalid_seniority():
    with pytest.raises(ValidationError):
        JDFeatures(
            salary_low=None,
            salary_high=None,
            salary_midpoint=None,
            comp_target=250000,
            jd_seniority="intern",
            candidate_seniority="staff",
            detected_archetype="AI Platform/LLMOps",
            target_archetypes=["AI Platform/LLMOps"],
            archetype_adjacency=1.0,
            requirements=[],
            org_signals=OrgSignals(
                glassdoor_rating=None,
                recent_layoffs=None,
                org_stability=3.0,
                remote_policy="unknown",
                location_fit=3.0,
            ),
            blockers=[],
        )


# --- ScoreResult ---

def test_score_result_valid():
    sr = ScoreResult(
        dimensions=[
            DimensionScore(name="CV Match", score=4.0, weight=0.25, weighted=1.0, reasoning="Strong match"),
        ],
        global_score=4.0,
        blocker_gate_active=False,
        blocker_gate_reason=None,
        interpretation="Good match -- worth applying",
        score_table="| ... |",
    )
    assert sr.global_score == 4.0
    assert sr.blocker_gate_active is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd "C:/Users/pachulc/OneDrive - Hasbro Inc/Documents/best-analytics/Python/external/career-ops" && python -m pytest tests/test_models.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'scoring'`

- [ ] **Step 4: Implement models.py**

```python
# scoring/models.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    text: str
    priority: Literal["must", "preferred", "nice"]
    match_strength: float = Field(ge=0.0, le=1.0)
    evidence: str


class OrgSignals(BaseModel):
    glassdoor_rating: float | None = Field(default=None, ge=1.0, le=5.0)
    recent_layoffs: bool | None = None
    org_stability: float = Field(ge=1.0, le=5.0)
    remote_policy: Literal["remote", "hybrid", "onsite", "unknown"]
    location_fit: float = Field(ge=1.0, le=5.0)


class Blocker(BaseModel):
    type: Literal["credentials", "citizenship", "experience_years", "domain", "geographic"]
    description: str
    severity: float = Field(ge=1.0, le=2.0)


class JDFeatures(BaseModel):
    # Comp
    salary_low: float | None = None
    salary_high: float | None = None
    salary_midpoint: float | None = None
    comp_target: float = Field(gt=0)

    # Level
    jd_seniority: Literal["junior", "mid", "senior", "staff", "principal", "director", "vp"]
    candidate_seniority: Literal["junior", "mid", "senior", "staff", "principal", "director", "vp"]

    # Archetype
    detected_archetype: str
    target_archetypes: list[str]
    archetype_adjacency: float = Field(ge=0.0, le=1.0)

    # CV Match
    requirements: list[Requirement]

    # Org Risk
    org_signals: OrgSignals

    # Blockers
    blockers: list[Blocker]


class DimensionScore(BaseModel):
    name: str
    score: float = Field(ge=1.0, le=5.0)
    weight: float
    weighted: float
    reasoning: str


class ScoreResult(BaseModel):
    dimensions: list[DimensionScore]
    global_score: float = Field(ge=1.0, le=5.0)
    blocker_gate_active: bool
    blocker_gate_reason: str | None = None
    interpretation: str
    score_table: str
```

```python
# scoring/__init__.py
from scoring.models import JDFeatures, ScoreResult
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/pachulc/OneDrive - Hasbro Inc/Documents/best-analytics/Python/external/career-ops" && python -m pytest tests/test_models.py -v`
Expected: All 12 tests PASS

- [ ] **Step 6: Commit**

```bash
git add scoring/__init__.py scoring/models.py tests/test_models.py
git commit -m "feat(scoring): add Pydantic input/output schemas"
```

---

### Task 2: score_comp_alignment

**Files:**
- Create: `scoring/engine.py`
- Modify: `tests/test_engine.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_engine.py
import pytest

from scoring.engine import score_comp_alignment


class TestScoreCompAlignment:
    def test_at_target(self):
        assert score_comp_alignment(250000, 250000, 250000) == 5.0

    def test_above_target(self):
        assert score_comp_alignment(300000, 400000, 250000) == 5.0

    def test_1_to_14_pct_below(self):
        # midpoint 225K is 90% of 250K -> 4.0
        assert score_comp_alignment(200000, 250000, 250000) == 4.0

    def test_15_to_29_pct_below(self):
        # midpoint 187.5K is 75% of 250K -> 3.0
        assert score_comp_alignment(175000, 200000, 250000) == 3.0

    def test_30_plus_pct_below(self):
        # midpoint 150K is 60% of 250K -> 2.0
        assert score_comp_alignment(100000, 200000, 250000) == 2.0

    def test_no_salary_info(self):
        assert score_comp_alignment(None, None, 250000) == 3.0

    def test_only_low_bound(self):
        # 250K is 100% of 250K -> 5.0
        assert score_comp_alignment(250000, None, 250000) == 5.0

    def test_only_high_bound(self):
        # 300K is 120% of 250K -> 5.0
        assert score_comp_alignment(None, 300000, 250000) == 5.0

    def test_midpoint_provided(self):
        # explicit midpoint 200K is 80% of 250K -> 3.0
        assert score_comp_alignment(None, None, 250000, salary_midpoint=200000) == 3.0

    def test_boundary_exactly_86_pct(self):
        # 215K / 250K = 0.86 -> 4.0 (inclusive lower bound)
        assert score_comp_alignment(215000, 215000, 250000) == 4.0

    def test_boundary_just_below_86_pct(self):
        # 214K / 250K = 0.856 -> 3.0
        assert score_comp_alignment(214000, 214000, 250000) == 3.0

    def test_boundary_exactly_71_pct(self):
        # 177.5K / 250K = 0.71 -> 3.0 (inclusive lower bound)
        assert score_comp_alignment(177500, 177500, 250000) == 3.0

    def test_boundary_just_below_71_pct(self):
        # 177K / 250K = 0.708 -> 2.0
        assert score_comp_alignment(177000, 177000, 250000) == 2.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestScoreCompAlignment -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'scoring.engine'`

- [ ] **Step 3: Implement score_comp_alignment**

```python
# scoring/engine.py
from __future__ import annotations


def score_comp_alignment(
    salary_low: float | None,
    salary_high: float | None,
    comp_target: float,
    *,
    salary_midpoint: float | None = None,
) -> float:
    """Score comp alignment based on effective salary vs target.

    Returns 1.0-5.0.
    """
    effective = _effective_salary(salary_low, salary_high, salary_midpoint)
    if effective is None:
        return 3.0

    ratio = effective / comp_target

    if ratio >= 1.0:
        return 5.0
    if ratio >= 0.86:
        return 4.0
    if ratio >= 0.71:
        return 3.0
    return 2.0


def _effective_salary(
    low: float | None,
    high: float | None,
    midpoint: float | None,
) -> float | None:
    """Derive a single salary figure from available data."""
    if midpoint is not None:
        return midpoint
    if low is not None and high is not None:
        return (low + high) / 2
    if low is not None:
        return low
    if high is not None:
        return high
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestScoreCompAlignment -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add score_comp_alignment with boundary tests"
```

---

### Task 3: score_level_fit

**Files:**
- Modify: `scoring/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_engine.py`:

```python
from scoring.engine import score_level_fit


class TestScoreLevelFit:
    def test_exact_match(self):
        assert score_level_fit("staff", "staff") == 5.0

    def test_one_up_stretch(self):
        assert score_level_fit("principal", "staff") == 4.0

    def test_one_down(self):
        assert score_level_fit("senior", "staff") == 3.0

    def test_two_up(self):
        assert score_level_fit("director", "staff") == 2.0

    def test_two_down(self):
        assert score_level_fit("mid", "staff") == 2.0

    def test_junior_to_vp(self):
        assert score_level_fit("vp", "junior") == 2.0

    def test_vp_to_junior(self):
        assert score_level_fit("junior", "vp") == 2.0

    def test_all_levels_exact_match(self):
        for level in ["junior", "mid", "senior", "staff", "principal", "director", "vp"]:
            assert score_level_fit(level, level) == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestScoreLevelFit -v`
Expected: FAIL -- `ImportError: cannot import name 'score_level_fit'`

- [ ] **Step 3: Implement score_level_fit**

Append to `scoring/engine.py`:

```python
_LEVEL_ORDER = {
    "junior": 0,
    "mid": 1,
    "senior": 2,
    "staff": 3,
    "principal": 4,
    "director": 5,
    "vp": 6,
}


def score_level_fit(jd_seniority: str, candidate_seniority: str) -> float:
    """Score level fit based on seniority delta.

    Returns 1.0-5.0.
    """
    delta = _LEVEL_ORDER[jd_seniority] - _LEVEL_ORDER[candidate_seniority]

    if delta == 0:
        return 5.0
    if delta == 1:
        return 4.0
    if delta == -1:
        return 3.0
    return 2.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestScoreLevelFit -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add score_level_fit"
```

---

### Task 4: score_archetype_fit

**Files:**
- Modify: `scoring/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_engine.py`:

```python
from scoring.engine import score_archetype_fit


class TestScoreArchetypeFit:
    def test_exact_match(self):
        assert score_archetype_fit(
            "AI Platform/LLMOps",
            ["AI Platform/LLMOps", "Agentic/Automation"],
            1.0,
        ) == 5.0

    def test_exact_match_low_adjacency_still_5(self):
        # adjacency is irrelevant when archetype is in target list
        assert score_archetype_fit(
            "AI Platform/LLMOps",
            ["AI Platform/LLMOps"],
            0.1,
        ) == 5.0

    def test_adjacent_high(self):
        # adjacency 0.8 -> 3.0 + (0.8 * 2.0) = 4.6, capped at 4.5
        assert score_archetype_fit(
            "Data Engineering",
            ["AI Platform/LLMOps"],
            0.8,
        ) == 4.5

    def test_adjacent_at_threshold(self):
        # adjacency 0.6 -> 3.0 + (0.6 * 2.0) = 4.2
        assert score_archetype_fit(
            "Data Engineering",
            ["AI Platform/LLMOps"],
            0.6,
        ) == 4.2

    def test_middle_zone(self):
        # adjacency 0.45 -> 2.5 + (0.45 * 2.5) = 3.625
        assert score_archetype_fit(
            "Product Analytics",
            ["AI Platform/LLMOps"],
            0.45,
        ) == 3.625

    def test_wrong_function_low(self):
        # adjacency 0.1 -> 1.0 + (0.1 * 5.0) = 1.5
        assert score_archetype_fit(
            "Marketing Analytics",
            ["AI Platform/LLMOps"],
            0.1,
        ) == 1.5

    def test_wrong_function_zero(self):
        # adjacency 0.0 -> 1.0 + (0.0 * 5.0) = 1.0
        assert score_archetype_fit(
            "HR Analytics",
            ["AI Platform/LLMOps"],
            0.0,
        ) == 1.0

    def test_boundary_just_below_06(self):
        # adjacency 0.59 -> middle zone: 2.5 + (0.59 * 2.5) = 3.975
        assert score_archetype_fit(
            "Data Engineering",
            ["AI Platform/LLMOps"],
            0.59,
        ) == 3.975

    def test_boundary_just_below_03(self):
        # adjacency 0.29 -> wrong function: 1.0 + (0.29 * 5.0) = 2.45
        assert score_archetype_fit(
            "Marketing",
            ["AI Platform/LLMOps"],
            0.29,
        ) == 2.45

    def test_boundary_exactly_03(self):
        # adjacency 0.3 -> middle zone: 2.5 + (0.3 * 2.5) = 3.25
        assert score_archetype_fit(
            "Analytics",
            ["AI Platform/LLMOps"],
            0.3,
        ) == 3.25
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestScoreArchetypeFit -v`
Expected: FAIL -- `ImportError: cannot import name 'score_archetype_fit'`

- [ ] **Step 3: Implement score_archetype_fit**

Append to `scoring/engine.py`:

```python
def score_archetype_fit(
    detected_archetype: str,
    target_archetypes: list[str],
    archetype_adjacency: float,
) -> float:
    """Score archetype fit based on match or adjacency.

    Returns 1.0-5.0.
    """
    if detected_archetype in target_archetypes:
        return 5.0

    if archetype_adjacency >= 0.6:
        return min(3.0 + archetype_adjacency * 2.0, 4.5)

    if archetype_adjacency < 0.3:
        return 1.0 + archetype_adjacency * 5.0

    return 2.5 + archetype_adjacency * 2.5
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestScoreArchetypeFit -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add score_archetype_fit"
```

---

### Task 5: score_cv_match

**Files:**
- Modify: `scoring/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_engine.py`:

```python
from scoring.engine import score_cv_match
from scoring.models import Requirement


class TestScoreCvMatch:
    def test_perfect_match_all_must(self):
        reqs = [
            Requirement(text="Python", priority="must", match_strength=1.0, evidence="7yr"),
            Requirement(text="SQL", priority="must", match_strength=1.0, evidence="7yr"),
        ]
        assert score_cv_match(reqs) == 5.0

    def test_zero_match_all_must(self):
        reqs = [
            Requirement(text="Go", priority="must", match_strength=0.0, evidence="none"),
            Requirement(text="Rust", priority="must", match_strength=0.0, evidence="none"),
        ]
        assert score_cv_match(reqs) == 1.0

    def test_mixed_priorities(self):
        reqs = [
            Requirement(text="Python", priority="must", match_strength=1.0, evidence="yes"),
            Requirement(text="Go", priority="preferred", match_strength=0.0, evidence="no"),
            Requirement(text="AWS", priority="nice", match_strength=0.5, evidence="some"),
        ]
        # weights: must=3, preferred=2, nice=1 -> total=6
        # weighted: (1.0*3 + 0.0*2 + 0.5*1) / 6 = 3.5/6 = 0.5833
        # score: 1.0 + 0.5833 * 4.0 = 3.333
        result = score_cv_match(reqs)
        assert abs(result - 3.333) < 0.01

    def test_empty_requirements(self):
        assert score_cv_match([]) == 3.0

    def test_all_preferred(self):
        reqs = [
            Requirement(text="Docker", priority="preferred", match_strength=0.8, evidence="yes"),
            Requirement(text="K8s", priority="preferred", match_strength=0.6, evidence="some"),
        ]
        # weighted: (0.8*2 + 0.6*2) / 4 = 2.8/4 = 0.7
        # score: 1.0 + 0.7 * 4.0 = 3.8
        assert score_cv_match(reqs) == 3.8

    def test_single_must_partial(self):
        reqs = [
            Requirement(text="ML", priority="must", match_strength=0.5, evidence="partial"),
        ]
        # score: 1.0 + 0.5 * 4.0 = 3.0
        assert score_cv_match(reqs) == 3.0

    def test_must_dominates_nice(self):
        reqs = [
            Requirement(text="Python", priority="must", match_strength=0.0, evidence="no"),
            Requirement(text="Bonus1", priority="nice", match_strength=1.0, evidence="yes"),
            Requirement(text="Bonus2", priority="nice", match_strength=1.0, evidence="yes"),
            Requirement(text="Bonus3", priority="nice", match_strength=1.0, evidence="yes"),
        ]
        # weights: must=3, 3x nice=1 each -> total=6
        # weighted: (0.0*3 + 1.0*1 + 1.0*1 + 1.0*1) / 6 = 3/6 = 0.5
        # score: 1.0 + 0.5 * 4.0 = 3.0
        assert score_cv_match(reqs) == 3.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestScoreCvMatch -v`
Expected: FAIL -- `ImportError: cannot import name 'score_cv_match'`

- [ ] **Step 3: Implement score_cv_match**

Append to `scoring/engine.py`:

```python
from scoring.models import Requirement


_PRIORITY_WEIGHTS = {"must": 3, "preferred": 2, "nice": 1}


def score_cv_match(requirements: list[Requirement]) -> float:
    """Score CV match as priority-weighted average of match strengths.

    Returns 1.0-5.0.
    """
    if not requirements:
        return 3.0

    weighted_sum = 0.0
    total_weight = 0.0

    for r in requirements:
        w = _PRIORITY_WEIGHTS[r.priority]
        weighted_sum += r.match_strength * w
        total_weight += w

    raw = weighted_sum / total_weight
    return 1.0 + raw * 4.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestScoreCvMatch -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add score_cv_match with priority weighting"
```

---

### Task 6: score_org_risk

**Files:**
- Modify: `scoring/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_engine.py`:

```python
from scoring.engine import score_org_risk
from scoring.models import OrgSignals


class TestScoreOrgRisk:
    def test_all_clean(self):
        signals = OrgSignals(
            glassdoor_rating=4.5,
            recent_layoffs=False,
            org_stability=5.0,
            remote_policy="remote",
            location_fit=5.0,
        )
        # (4.5 + 5.0 + 5.0 + 5.0 + 5.0) / 5 = 4.9
        assert score_org_risk(signals) == 4.9

    def test_all_bad(self):
        signals = OrgSignals(
            glassdoor_rating=1.5,
            recent_layoffs=True,
            org_stability=1.0,
            remote_policy="onsite",
            location_fit=1.0,
        )
        # (1.5 + 2.0 + 1.0 + 2.5 + 1.0) / 5 = 1.6
        assert score_org_risk(signals) == 1.6

    def test_missing_glassdoor_and_layoffs(self):
        signals = OrgSignals(
            glassdoor_rating=None,
            recent_layoffs=None,
            org_stability=4.0,
            remote_policy="hybrid",
            location_fit=3.0,
        )
        # (4.0 + 4.0 + 3.0) / 3 = 3.667
        result = score_org_risk(signals)
        assert abs(result - 3.667) < 0.01

    def test_remote_policy_mapping(self):
        for policy, expected in [("remote", 5.0), ("hybrid", 4.0), ("onsite", 2.5), ("unknown", 3.0)]:
            signals = OrgSignals(
                glassdoor_rating=None,
                recent_layoffs=None,
                org_stability=expected,
                remote_policy=policy,
                location_fit=expected,
            )
            result = score_org_risk(signals)
            assert abs(result - expected) < 0.01, f"Failed for {policy}"

    def test_layoffs_true(self):
        signals = OrgSignals(
            glassdoor_rating=None,
            recent_layoffs=True,
            org_stability=5.0,
            remote_policy="remote",
            location_fit=5.0,
        )
        # (2.0 + 5.0 + 5.0 + 5.0) / 4 = 4.25
        assert score_org_risk(signals) == 4.25

    def test_layoffs_false(self):
        signals = OrgSignals(
            glassdoor_rating=None,
            recent_layoffs=False,
            org_stability=5.0,
            remote_policy="remote",
            location_fit=5.0,
        )
        # (5.0 + 5.0 + 5.0 + 5.0) / 4 = 5.0
        assert score_org_risk(signals) == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestScoreOrgRisk -v`
Expected: FAIL -- `ImportError: cannot import name 'score_org_risk'`

- [ ] **Step 3: Implement score_org_risk**

Append to `scoring/engine.py`:

```python
from scoring.models import OrgSignals

_REMOTE_POLICY_SCORES = {
    "remote": 5.0,
    "hybrid": 4.0,
    "onsite": 2.5,
    "unknown": 3.0,
}


def score_org_risk(org_signals: OrgSignals) -> float:
    """Score org risk as mean of available signal scores.

    Returns 1.0-5.0.
    """
    scores: list[float] = []

    if org_signals.glassdoor_rating is not None:
        scores.append(org_signals.glassdoor_rating)

    if org_signals.recent_layoffs is not None:
        scores.append(2.0 if org_signals.recent_layoffs else 5.0)

    scores.append(org_signals.org_stability)
    scores.append(_REMOTE_POLICY_SCORES[org_signals.remote_policy])
    scores.append(org_signals.location_fit)

    return sum(scores) / len(scores)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestScoreOrgRisk -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add score_org_risk"
```

---

### Task 7: score_blockers

**Files:**
- Modify: `scoring/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_engine.py`:

```python
from scoring.engine import score_blockers
from scoring.models import Blocker


class TestScoreBlockers:
    def test_no_blockers(self):
        assert score_blockers([]) == 5.0

    def test_single_absolute_blocker(self):
        blockers = [Blocker(type="citizenship", description="US only", severity=1.0)]
        assert score_blockers(blockers) == 1.0

    def test_single_difficult_blocker(self):
        blockers = [Blocker(type="experience_years", description="15yr req", severity=2.0)]
        assert score_blockers(blockers) == 2.0

    def test_multiple_blockers_uses_min(self):
        blockers = [
            Blocker(type="citizenship", description="US only", severity=1.0),
            Blocker(type="experience_years", description="15yr", severity=1.5),
        ]
        assert score_blockers(blockers) == 1.0

    def test_mid_severity(self):
        blockers = [Blocker(type="domain", description="adtech", severity=1.5)]
        assert score_blockers(blockers) == 1.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestScoreBlockers -v`
Expected: FAIL -- `ImportError: cannot import name 'score_blockers'`

- [ ] **Step 3: Implement score_blockers**

Append to `scoring/engine.py`:

```python
from scoring.models import Blocker


def score_blockers(blockers: list[Blocker]) -> float:
    """Score blockers dimension. No blockers = 5.0, otherwise min severity.

    Returns 1.0-5.0.
    """
    if not blockers:
        return 5.0
    return min(b.severity for b in blockers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestScoreBlockers -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add score_blockers"
```

---

### Task 8: compute_global + ScoreResult builder

**Files:**
- Modify: `scoring/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_engine.py`:

```python
from scoring.engine import compute_global
from scoring.models import JDFeatures, OrgSignals, Requirement, Blocker


def _make_features(**overrides) -> JDFeatures:
    """Helper to build JDFeatures with sensible defaults."""
    defaults = dict(
        salary_low=250000,
        salary_high=300000,
        salary_midpoint=None,
        comp_target=250000,
        jd_seniority="staff",
        candidate_seniority="staff",
        detected_archetype="AI Platform/LLMOps",
        target_archetypes=["AI Platform/LLMOps"],
        archetype_adjacency=1.0,
        requirements=[
            Requirement(text="Python", priority="must", match_strength=0.9, evidence="yes"),
            Requirement(text="SQL", priority="must", match_strength=0.8, evidence="yes"),
        ],
        org_signals=OrgSignals(
            glassdoor_rating=4.0,
            recent_layoffs=False,
            org_stability=4.5,
            remote_policy="remote",
            location_fit=5.0,
        ),
        blockers=[],
    )
    defaults.update(overrides)
    return JDFeatures(**defaults)


class TestComputeGlobal:
    def test_strong_match_no_blockers(self):
        features = _make_features()
        result = compute_global(features)
        assert result.blocker_gate_active is False
        # CV: 1+0.85*4=4.4, Archetype: 5.0, Comp: 5.0, Level: 5.0, Org: ~4.5, Blockers: 5.0
        # weighted: 4.4*.25 + 5.0*.20 + 5.0*.20 + 5.0*.15 + 4.5*.10 + 5.0*.10
        # = 1.1 + 1.0 + 1.0 + 0.75 + 0.45 + 0.5 = 4.8
        assert result.global_score >= 4.5

    def test_blocker_gate_caps_at_25(self):
        features = _make_features(
            blockers=[Blocker(type="citizenship", description="US only", severity=1.0)],
        )
        result = compute_global(features)
        assert result.blocker_gate_active is True
        assert result.global_score <= 2.5
        assert "US only" in result.blocker_gate_reason

    def test_truncation_never_rounds_up(self):
        # Construct features that would produce e.g. 3.49x
        # The global should stay at 3.4, not round to 3.5
        features = _make_features(
            salary_low=200000,
            salary_high=220000,
            detected_archetype="Adjacent Role",
            target_archetypes=["AI Platform/LLMOps"],
            archetype_adjacency=0.5,
            requirements=[
                Requirement(text="Python", priority="must", match_strength=0.7, evidence="yes"),
            ],
        )
        result = compute_global(features)
        # Verify truncation: score * 10 should be an integer (one decimal place)
        assert result.global_score == int(result.global_score * 10) / 10

    def test_score_table_contains_all_dimensions(self):
        features = _make_features()
        result = compute_global(features)
        for dim_name in ["CV Match", "Archetype Fit", "Comp Alignment", "Level Fit", "Org Risk", "Blockers"]:
            assert dim_name in result.score_table

    def test_interpretation_strong_match(self):
        features = _make_features()
        result = compute_global(features)
        assert "Strong match" in result.interpretation or "Good match" in result.interpretation

    def test_interpretation_below_threshold(self):
        features = _make_features(
            salary_low=100000,
            salary_high=120000,
            detected_archetype="Wrong Field",
            target_archetypes=["AI Platform/LLMOps"],
            archetype_adjacency=0.1,
            jd_seniority="junior",
            requirements=[
                Requirement(text="Go", priority="must", match_strength=0.1, evidence="none"),
            ],
            org_signals=OrgSignals(
                glassdoor_rating=2.0,
                recent_layoffs=True,
                org_stability=2.0,
                remote_policy="onsite",
                location_fit=1.0,
            ),
        )
        result = compute_global(features)
        assert result.global_score < 3.5
        assert "Below threshold" in result.interpretation

    def test_dimensions_list_has_six_entries(self):
        features = _make_features()
        result = compute_global(features)
        assert len(result.dimensions) == 6

    def test_weighted_values_sum_to_global(self):
        features = _make_features()
        result = compute_global(features)
        weighted_sum = sum(d.weighted for d in result.dimensions)
        # truncated global should be <= raw weighted sum
        assert result.global_score <= weighted_sum + 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py::TestComputeGlobal -v`
Expected: FAIL -- `ImportError: cannot import name 'compute_global'`

- [ ] **Step 3: Implement compute_global**

Append to `scoring/engine.py`:

```python
import math

from scoring.models import JDFeatures, ScoreResult, DimensionScore


_WEIGHTS = {
    "CV Match": 0.25,
    "Archetype Fit": 0.20,
    "Comp Alignment": 0.20,
    "Level Fit": 0.15,
    "Org Risk": 0.10,
    "Blockers": 0.10,
}

_INTERPRETATIONS = [
    (4.5, "Strong match -- recommend applying immediately"),
    (4.0, "Good match -- worth applying"),
    (3.5, "Decent but not ideal -- apply only with specific reason"),
    (0.0, "Below threshold -- recommend against applying"),
]


def _truncate_one_decimal(value: float) -> float:
    """Truncate to one decimal place. Never rounds up."""
    return math.floor(value * 10) / 10


def _format_score_table(dimensions: list[DimensionScore], global_score: float) -> str:
    """Format the markdown score table for reports."""
    lines = [
        "| Dimension | Score | Weight | Weighted |",
        "|-----------|-------|--------|----------|",
    ]
    for d in dimensions:
        pct = f"{int(d.weight * 100)}%"
        lines.append(f"| {d.name} | {d.score:.1f} | {pct} | {d.weighted:.2f} |")
    lines.append(f"| **Global** | | | **{global_score:.1f}/5** |")
    return "\n".join(lines)


def compute_global(features: JDFeatures) -> ScoreResult:
    """Compute all 6 dimension scores and the blocker-gated global score.

    This is the main entry point. Pure function: no I/O, no side effects.
    """
    dim_scores = {
        "CV Match": score_cv_match(features.requirements),
        "Archetype Fit": score_archetype_fit(
            features.detected_archetype,
            features.target_archetypes,
            features.archetype_adjacency,
        ),
        "Comp Alignment": score_comp_alignment(
            features.salary_low,
            features.salary_high,
            features.comp_target,
            salary_midpoint=features.salary_midpoint,
        ),
        "Level Fit": score_level_fit(
            features.jd_seniority,
            features.candidate_seniority,
        ),
        "Org Risk": score_org_risk(features.org_signals),
        "Blockers": score_blockers(features.blockers),
    }

    dimensions = []
    raw_global = 0.0

    for name, score in dim_scores.items():
        weight = _WEIGHTS[name]
        weighted = round(score * weight, 4)
        raw_global += weighted
        dimensions.append(DimensionScore(
            name=name,
            score=round(score, 1),
            weight=weight,
            weighted=round(weighted, 2),
            reasoning="",  # filled by caller or Claude
        ))

    blocker_gate_active = len(features.blockers) > 0
    blocker_gate_reason = None

    if blocker_gate_active:
        blocker_gate_reason = "; ".join(b.description for b in features.blockers)
        raw_global = min(raw_global, 2.5)

    global_score = _truncate_one_decimal(raw_global)
    global_score = max(1.0, min(5.0, global_score))

    interpretation = ""
    for threshold, text in _INTERPRETATIONS:
        if global_score >= threshold:
            interpretation = text
            break

    score_table = _format_score_table(dimensions, global_score)

    return ScoreResult(
        dimensions=dimensions,
        global_score=global_score,
        blocker_gate_active=blocker_gate_active,
        blocker_gate_reason=blocker_gate_reason,
        interpretation=interpretation,
        score_table=score_table,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py::TestComputeGlobal -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (models + all engine tests)

- [ ] **Step 6: Commit**

```bash
git add scoring/engine.py tests/test_engine.py
git commit -m "feat(scoring): add compute_global with blocker gate and score table"
```

---

### Task 9: CLI Entry Point

**Files:**
- Create: `scoring/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli.py
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run_cli(input_json: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scoring.cli"],
        input=input_json,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def _valid_input() -> dict:
    return {
        "salary_low": 250000,
        "salary_high": 300000,
        "salary_midpoint": None,
        "comp_target": 250000,
        "jd_seniority": "staff",
        "candidate_seniority": "staff",
        "detected_archetype": "AI Platform/LLMOps",
        "target_archetypes": ["AI Platform/LLMOps"],
        "archetype_adjacency": 1.0,
        "requirements": [
            {"text": "Python", "priority": "must", "match_strength": 0.9, "evidence": "yes"},
        ],
        "org_signals": {
            "glassdoor_rating": 4.0,
            "recent_layoffs": False,
            "org_stability": 4.5,
            "remote_policy": "remote",
            "location_fit": 5.0,
        },
        "blockers": [],
    }


class TestCli:
    def test_valid_input_exits_0(self):
        result = _run_cli(json.dumps(_valid_input()))
        assert result.returncode == 0

    def test_valid_input_returns_json(self):
        result = _run_cli(json.dumps(_valid_input()))
        output = json.loads(result.stdout)
        assert "global_score" in output
        assert "dimensions" in output
        assert "score_table" in output

    def test_invalid_json_exits_1(self):
        result = _run_cli("not json at all")
        assert result.returncode == 1

    def test_missing_required_field_exits_1(self):
        bad = _valid_input()
        del bad["comp_target"]
        result = _run_cli(json.dumps(bad))
        assert result.returncode == 1

    def test_file_input(self, tmp_path):
        f = tmp_path / "features.json"
        f.write_text(json.dumps(_valid_input()))
        result = subprocess.run(
            [sys.executable, "-m", "scoring.cli", "--input", str(f)],
            capture_output=True,
            text=True,
            cwd=str(REPO),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "global_score" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL -- `No module named scoring.cli`

- [ ] **Step 3: Implement cli.py**

```python
# scoring/cli.py
"""CLI entry point for the scoring engine.

Usage:
    echo '{"salary_low": ...}' | python -m scoring.cli
    python -m scoring.cli --input features.json
"""
from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from scoring.models import JDFeatures
from scoring.engine import compute_global


def main() -> int:
    parser = argparse.ArgumentParser(description="career-ops scoring engine")
    parser.add_argument("--input", type=str, help="Path to JDFeatures JSON file (reads stdin if omitted)")
    args = parser.parse_args()

    try:
        if args.input:
            with open(args.input) as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()

        data = json.loads(raw)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1

    try:
        features = JDFeatures(**data)
    except ValidationError as e:
        print(json.dumps({"error": e.errors()}), file=sys.stderr)
        return 1

    result = compute_global(features)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# scoring/__main__.py support
```

Also create `scoring/__main__.py`:

```python
# scoring/__main__.py
from scoring.cli import main
import sys

sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scoring/cli.py scoring/__main__.py tests/test_cli.py
git commit -m "feat(scoring): add CLI entry point with stdin and file input"
```

---

### Task 10: Calibrate Against Existing Reports

**Files:**
- Create: `scoring/calibrate.py`

- [ ] **Step 1: Write the calibration script**

```python
# scoring/calibrate.py
"""Back-test scoring engine against existing evaluation reports.

Parses reports in reports/ for:
- Global scores (all 67 reports)
- Dimension breakdowns (9 reports with score tables)

Outputs comparison CSV and summary statistics.

Usage:
    python -m scoring.calibrate --reports-dir reports/
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


def parse_global_score(text: str) -> float | None:
    """Extract global score from report header."""
    match = re.search(r"\*\*Score:\*\*\s*([\d.]+)/5", text)
    if match:
        return float(match.group(1))
    return None


def parse_score_table(text: str) -> dict[str, float] | None:
    """Extract dimension scores from score breakdown table."""
    # Match rows like: | CV Match | 25% | 3.0 | 0.75 |
    # or:              | CV Match | 3.0 | 25% | 0.75 |
    # Column order varies between reports
    pattern = re.compile(
        r"\|\s*(CV Match|Archetype Fit|Comp Alignment|Level Fit|Org Risk|Blockers)\s*\|"
        r"\s*([\d.]+%?)\s*\|\s*([\d.]+%?)\s*\|\s*([\d.]+)\s*\|"
    )

    scores = {}
    for match in pattern.finditer(text):
        name = match.group(1)
        col2 = match.group(2)
        col3 = match.group(3)

        # Determine which column is the score (no %) and which is weight (has %)
        if "%" in col2:
            score = float(col3)
        else:
            score = float(col2)

        scores[name] = score

    if len(scores) == 6:
        return scores
    return None


def parse_report(path: Path) -> dict:
    """Parse a single report file."""
    text = path.read_text(encoding="utf-8")

    return {
        "file": path.name,
        "global_score": parse_global_score(text),
        "dimensions": parse_score_table(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate scoring engine against existing reports")
    parser.add_argument("--reports-dir", type=str, default="reports/")
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        print(f"Reports directory not found: {reports_dir}", file=sys.stderr)
        return 1

    reports = []
    for path in sorted(reports_dir.glob("*.md")):
        parsed = parse_report(path)
        if parsed["global_score"] is not None:
            reports.append(parsed)

    if not reports:
        print("No reports with scores found.", file=sys.stderr)
        return 1

    # Summary
    global_scores = [r["global_score"] for r in reports]
    with_tables = [r for r in reports if r["dimensions"] is not None]

    print(f"\nReports parsed: {len(reports)}")
    print(f"Reports with score tables: {len(with_tables)}")
    print(f"Global score range: {min(global_scores):.1f} - {max(global_scores):.1f}")
    print(f"Global score mean: {sum(global_scores) / len(global_scores):.2f}")
    print(f"Global score median: {sorted(global_scores)[len(global_scores) // 2]:.1f}")

    if with_tables:
        print("\n--- Dimension Score Distribution (from score tables) ---\n")

        dim_data = []
        for r in with_tables:
            for dim_name, dim_score in r["dimensions"].items():
                dim_data.append({
                    "file": r["file"],
                    "dimension": dim_name,
                    "score": dim_score,
                    "global": r["global_score"],
                })

        df = pd.DataFrame(dim_data)
        summary = df.groupby("dimension")["score"].agg(["mean", "std", "min", "max", "count"])
        print(summary.to_string())

        # Per-report breakdown
        print("\n--- Per-Report Score Table Comparison ---\n")
        for r in with_tables:
            print(f"\n{r['file']} (global: {r['global_score']})")
            for dim, score in r["dimensions"].items():
                print(f"  {dim}: {score}")

    # Write CSV for further analysis
    csv_path = reports_dir.parent / "data" / "calibration-results.tsv"
    rows = []
    for r in reports:
        row = {"file": r["file"], "global_score": r["global_score"]}
        if r["dimensions"]:
            row.update(r["dimensions"])
        rows.append(row)

    df_out = pd.DataFrame(rows)
    df_out.to_csv(csv_path, sep="\t", index=False)
    print(f"\nCalibration results written to: {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the calibration**

Run: `cd "C:/Users/pachulc/OneDrive - Hasbro Inc/Documents/best-analytics/Python/external/career-ops" && python -m scoring.calibrate --reports-dir reports/`

Review output: verify it parses all 67 global scores and 9 dimension breakdowns.

- [ ] **Step 3: Commit**

```bash
git add scoring/calibrate.py
git commit -m "feat(scoring): add calibration script for back-testing against reports"
```

---

### Task 11: Mode Integration

**Files:**
- Modify: `modes/_shared.md` (scoring section)
- Modify: `modes/evaluate.md` (add extraction schema reference)

- [ ] **Step 1: Update _shared.md scoring section**

Replace the "Scoring System" section in `modes/_shared.md` (lines 26-103) with engine invocation instructions. Keep the dimension definitions as documentation but add:

```markdown
## Scoring System

The evaluation uses a deterministic Python scoring engine in `scoring/`. Claude's role is to extract structured features from the JD; the engine computes all scores.

### Feature Extraction

After analyzing the JD (blocks A-F), fill the JDFeatures schema and run the engine:

1. Write a JSON file matching the `scoring.models.JDFeatures` schema (see `scoring/models.py` for the full definition)
2. Run: `python -m scoring.cli --input /tmp/jd-features.json`
3. The engine returns a `ScoreResult` JSON with all dimension scores, the global score, blocker gate status, interpretation, and a pre-formatted markdown score table
4. Use the `score_table` field directly in the report
5. Use the `interpretation` field for the recommendation
6. Do NOT compute scores manually -- the engine is the source of truth

### Dimension Reference (for feature extraction guidance)

[Keep existing dimension table and blocker gate criteria as-is -- Claude needs these to correctly extract features]

### Calibration Benchmarks

[Keep existing benchmarks -- useful for sanity-checking engine output]
```

- [ ] **Step 2: Update modes/evaluate.md**

Add a note after the Block F section referencing the scoring engine:

```markdown
## Scoring

After completing blocks A-F, extract JD features into the `JDFeatures` schema and run the scoring engine. See `modes/_shared.md` "Scoring System" section for the extraction and invocation workflow. The engine output includes the score table and interpretation -- use them directly in the report.
```

- [ ] **Step 3: Commit**

```bash
git add modes/_shared.md modes/evaluate.md
git commit -m "feat(scoring): integrate engine with evaluation modes"
```

---

## Execution Order

Tasks 1-9 are strictly sequential (each builds on the previous). Task 10 requires Tasks 1-8. Task 11 is independent of Task 10.

```
Task 1 (models) -> Task 2 (comp) -> Task 3 (level) -> Task 4 (archetype)
  -> Task 5 (cv_match) -> Task 6 (org_risk) -> Task 7 (blockers)
  -> Task 8 (compute_global) -> Task 9 (cli) -> Task 10 (calibrate)
                                              -> Task 11 (mode integration)
```

Total: 11 tasks, ~55 steps, ~11 commits.
