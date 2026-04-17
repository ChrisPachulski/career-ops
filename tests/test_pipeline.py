from __future__ import annotations

import pytest

from scoring.diagnostics import build_trace
from scoring.engine import evaluate
from scoring.models import (
    Blocker,
    BlockerGate,
    CompThresholds,
    DiagnosticStep,
    DiagnosticTrace,
    JDFeatures,
    OrgSignals,
    Requirement,
    ScoreConfig,
    Warning,
)


###############################################################################
# Shared fixture builder
###############################################################################


def _make_features(**overrides) -> JDFeatures:
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


###############################################################################
# scoring.diagnostics -- build_trace
###############################################################################


def test_build_trace_returns_six_steps():
    features = _make_features()
    dim_scores = {
        "Comp Alignment": 5.0,
        "Level Fit": 5.0,
        "Archetype Fit": 5.0,
        "CV Match": 4.6,
        "Org Risk": 4.5,
        "Blockers": 5.0,
    }
    trace = build_trace(features, dim_scores, ScoreConfig())
    assert isinstance(trace, DiagnosticTrace)
    assert len(trace.steps) == 6


def test_build_trace_each_step_is_diagnostic_step():
    features = _make_features()
    dim_scores = {
        "Comp Alignment": 5.0,
        "Level Fit": 5.0,
        "Archetype Fit": 5.0,
        "CV Match": 4.6,
        "Org Risk": 4.5,
        "Blockers": 5.0,
    }
    trace = build_trace(features, dim_scores, ScoreConfig())
    for step in trace.steps:
        assert isinstance(step, DiagnosticStep)


def test_build_trace_step_has_required_fields():
    features = _make_features()
    dim_scores = {
        "Comp Alignment": 5.0,
        "Level Fit": 5.0,
        "Archetype Fit": 5.0,
        "CV Match": 4.6,
        "Org Risk": 4.5,
        "Blockers": 5.0,
    }
    trace = build_trace(features, dim_scores, ScoreConfig())
    for step in trace.steps:
        assert isinstance(step.dimension, str) and step.dimension
        assert isinstance(step.inputs, dict)
        assert isinstance(step.computation, str) and step.computation
        assert isinstance(step.threshold_hit, str) and step.threshold_hit
        assert isinstance(step.sensitivity, list)


def test_build_trace_covers_all_six_dimensions():
    features = _make_features()
    dim_scores = {
        "Comp Alignment": 5.0,
        "Level Fit": 5.0,
        "Archetype Fit": 5.0,
        "CV Match": 4.6,
        "Org Risk": 4.5,
        "Blockers": 5.0,
    }
    trace = build_trace(features, dim_scores, ScoreConfig())
    dimension_names = {step.dimension for step in trace.steps}
    expected = {"Comp Alignment", "Level Fit", "Archetype Fit", "CV Match", "Org Risk", "Blockers"}
    assert dimension_names == expected


def test_build_trace_comp_shows_sensitivity_when_below_target():
    features = _make_features(salary_low=200000, salary_high=220000)
    dim_scores = {"Comp Alignment": 4.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    comp_step = next(s for s in trace.steps if s.dimension == "Comp Alignment")
    assert len(comp_step.sensitivity) > 0


def test_build_trace_comp_no_sensitivity_when_at_or_above_target():
    features = _make_features(salary_low=260000, salary_high=300000)
    dim_scores = {"Comp Alignment": 5.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    comp_step = next(s for s in trace.steps if s.dimension == "Comp Alignment")
    assert comp_step.sensitivity == []


def test_build_trace_comp_default_when_no_salary():
    features = _make_features(salary_low=None, salary_high=None, salary_midpoint=None)
    dim_scores = {"Comp Alignment": 3.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    comp_step = next(s for s in trace.steps if s.dimension == "Comp Alignment")
    assert "default" in comp_step.computation.lower()


def test_build_trace_blockers_step_shows_zero_when_none():
    features = _make_features(blockers=[])
    dim_scores = {"Blockers": 5.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    blocker_step = next(s for s in trace.steps if s.dimension == "Blockers")
    assert blocker_step.inputs.get("count") == "0"
    assert "no blockers" in blocker_step.computation.lower()


def test_build_trace_blockers_step_lists_blockers_when_present():
    blockers = [
        Blocker(type="citizenship", description="US only", severity=1.0),
        Blocker(type="domain", description="Needs clearance", severity=1.5),
    ]
    features = _make_features(blockers=blockers)
    dim_scores = {"Blockers": 1.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    blocker_step = next(s for s in trace.steps if s.dimension == "Blockers")
    assert "citizenship" in blocker_step.inputs
    assert "domain" in blocker_step.inputs


def test_build_trace_level_shows_exact_match():
    features = _make_features(jd_seniority="staff", candidate_seniority="staff")
    dim_scores = {"Level Fit": 5.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    level_step = next(s for s in trace.steps if s.dimension == "Level Fit")
    assert "exact match" in level_step.computation.lower()


def test_build_trace_archetype_shows_exact_match():
    features = _make_features(
        detected_archetype="AI Platform/LLMOps",
        target_archetypes=["AI Platform/LLMOps"],
    )
    dim_scores = {"Archetype Fit": 5.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    arch_step = next(s for s in trace.steps if s.dimension == "Archetype Fit")
    assert "exact match" in arch_step.computation.lower()


def test_build_trace_archetype_shows_adjacency_when_not_exact():
    features = _make_features(
        detected_archetype="data-scientist",
        target_archetypes=["AI Platform/LLMOps"],
        archetype_adjacency=0.7,
    )
    dim_scores = {"Archetype Fit": 4.0}
    trace = build_trace(features, dim_scores, ScoreConfig())
    arch_step = next(s for s in trace.steps if s.dimension == "Archetype Fit")
    assert "adjacency" in arch_step.computation.lower()


###############################################################################
# scoring.engine.evaluate -- diagnostics flag
###############################################################################


def test_evaluate_without_diagnostics_returns_none_trace():
    result = evaluate(_make_features(), diagnostics=False)
    assert result.diagnostic_trace is None


def test_evaluate_with_diagnostics_returns_trace():
    result = evaluate(_make_features(), diagnostics=True)
    assert result.diagnostic_trace is not None
    assert isinstance(result.diagnostic_trace, DiagnosticTrace)


def test_evaluate_with_diagnostics_has_six_steps():
    result = evaluate(_make_features(), diagnostics=True)
    assert len(result.diagnostic_trace.steps) == 6


def test_evaluate_default_diagnostics_is_false():
    result = evaluate(_make_features())
    assert result.diagnostic_trace is None


###############################################################################
# scoring.engine.evaluate -- normalization warnings
###############################################################################


def test_evaluate_collects_normalization_warning_for_high_mean_match_strength():
    """4+ requirements with mean match_strength > 0.85 triggers dampening."""
    reqs = [
        Requirement(text="Python", priority="must", match_strength=0.95, evidence="yes"),
        Requirement(text="SQL", priority="must", match_strength=0.90, evidence="yes"),
        Requirement(text="ML", priority="preferred", match_strength=0.92, evidence="yes"),
        Requirement(text="Cloud", priority="nice", match_strength=0.88, evidence="yes"),
    ]
    result = evaluate(_make_features(requirements=reqs))
    dampening_warnings = [w for w in result.warnings if w.code == "MATCH_STRENGTH_DAMPENED"]
    assert len(dampening_warnings) == 1
    assert dampening_warnings[0].tier == "pre_computation"


def test_evaluate_no_normalization_warning_when_mean_below_threshold():
    """4+ requirements with mean match_strength <= 0.85 should NOT trigger dampening."""
    reqs = [
        Requirement(text="Python", priority="must", match_strength=0.70, evidence="yes"),
        Requirement(text="SQL", priority="must", match_strength=0.60, evidence="yes"),
        Requirement(text="ML", priority="preferred", match_strength=0.80, evidence="yes"),
        Requirement(text="Cloud", priority="nice", match_strength=0.50, evidence="yes"),
    ]
    result = evaluate(_make_features(requirements=reqs))
    dampening_warnings = [w for w in result.warnings if w.code == "MATCH_STRENGTH_DAMPENED"]
    assert len(dampening_warnings) == 0


def test_evaluate_no_normalization_warning_when_fewer_than_4_requirements():
    """Fewer than 4 requirements should NOT trigger dampening even with high mean."""
    reqs = [
        Requirement(text="Python", priority="must", match_strength=0.95, evidence="yes"),
        Requirement(text="SQL", priority="must", match_strength=0.95, evidence="yes"),
    ]
    result = evaluate(_make_features(requirements=reqs))
    dampening_warnings = [w for w in result.warnings if w.code == "MATCH_STRENGTH_DAMPENED"]
    assert len(dampening_warnings) == 0


###############################################################################
# scoring.engine.evaluate -- validation warnings
###############################################################################


def test_evaluate_collects_salary_inverted_warning():
    """salary_low > salary_high triggers SALARY_INVERTED."""
    result = evaluate(_make_features(salary_low=300000, salary_high=200000))
    inverted = [w for w in result.warnings if w.code == "SALARY_INVERTED"]
    assert len(inverted) == 1
    assert inverted[0].tier == "pre_computation"


def test_evaluate_collects_uniform_match_strength_warning():
    """3+ requirements with identical match_strength triggers UNIFORM_MATCH_STRENGTH."""
    reqs = [
        Requirement(text="Python", priority="must", match_strength=0.80, evidence="yes"),
        Requirement(text="SQL", priority="must", match_strength=0.80, evidence="yes"),
        Requirement(text="ML", priority="preferred", match_strength=0.80, evidence="yes"),
    ]
    result = evaluate(_make_features(requirements=reqs))
    uniform = [w for w in result.warnings if w.code == "UNIFORM_MATCH_STRENGTH"]
    assert len(uniform) == 1


def test_evaluate_collects_adjacency_with_exact_match_warning():
    """Exact archetype match but adjacency < 1.0 triggers warning."""
    result = evaluate(_make_features(
        detected_archetype="AI Platform/LLMOps",
        target_archetypes=["AI Platform/LLMOps"],
        archetype_adjacency=0.5,
    ))
    adj_warnings = [w for w in result.warnings if w.code == "ADJACENCY_WITH_EXACT_MATCH"]
    assert len(adj_warnings) == 1


def test_evaluate_collects_salary_point_estimate_warning():
    """salary_low == salary_high with no midpoint triggers SALARY_POINT_ESTIMATE."""
    result = evaluate(_make_features(salary_low=200000, salary_high=200000, salary_midpoint=None))
    point_est = [w for w in result.warnings if w.code == "SALARY_POINT_ESTIMATE"]
    assert len(point_est) == 1


def test_evaluate_collects_post_computation_match_blocker_contradiction():
    """High CV Match (>= 4.5) with hard blockers (<= 2.0) triggers contradiction warning."""
    reqs = [
        Requirement(text="Python", priority="must", match_strength=1.0, evidence="yes"),
        Requirement(text="SQL", priority="must", match_strength=1.0, evidence="yes"),
    ]
    blocker = Blocker(type="citizenship", description="US only", severity=1.0)
    result = evaluate(_make_features(requirements=reqs, blockers=[blocker]))
    contradiction = [w for w in result.warnings if w.code == "MATCH_BLOCKER_CONTRADICTION"]
    assert len(contradiction) == 1
    assert contradiction[0].tier == "post_computation"


def test_evaluate_warnings_list_is_empty_when_no_issues():
    """Clean features with no edge cases produce no warnings."""
    result = evaluate(_make_features())
    assert result.warnings == []


###############################################################################
# scoring.engine.evaluate -- graduated blocker gate
###############################################################################


def test_blocker_severity_1_0_caps_global_at_2_0():
    """Severity 1.0 (absolute blocker) should cap global score at 2.0."""
    blocker = Blocker(type="citizenship", description="US only", severity=1.0)
    result = evaluate(_make_features(blockers=[blocker]))
    assert result.global_score <= 2.0
    assert result.blocker_gate_active is True


def test_blocker_severity_1_5_caps_global_at_3_0():
    """Severity 1.5 (medium blocker) should cap global score at 3.0."""
    blocker = Blocker(type="domain", description="Needs clearance", severity=1.5)
    result = evaluate(_make_features(blockers=[blocker]))
    assert result.global_score <= 3.0
    assert result.blocker_gate_active is True


def test_blocker_severity_1_8_reduces_by_0_5():
    """Severity 1.8 (soft blocker) should reduce global by 0.5, not cap."""
    blocker = Blocker(type="experience_years", description="10+ years preferred", severity=1.8)

    result_no_blocker = evaluate(_make_features(blockers=[]))
    result_with_blocker = evaluate(_make_features(blockers=[blocker]))

    # Soft penalty subtracts 0.5 from the raw global.
    # The blocker itself also contributes to the weighted score (dimension score
    # drops from 5.0 to 1.8 * weight), so the raw global changes.
    # We verify: (a) gate active, (b) not hard-capped, (c) score is lower.
    assert result_with_blocker.blocker_gate_active is True
    assert result_with_blocker.global_score < result_no_blocker.global_score
    # Severity 1.8 > medium_max_severity=1.6, so it hits the soft penalty path,
    # meaning score is NOT hard-capped at 2.0 or 3.0.
    # A strong match (>= 4.5) minus 0.5 and dimension penalty should still be > 3.0
    assert result_with_blocker.global_score > 3.0


def test_blocker_severity_exactly_at_hard_boundary():
    """Severity 1.3 (== hard_max_severity) should cap at hard_cap=2.0."""
    blocker = Blocker(type="credentials", description="Needs PhD", severity=1.3)
    result = evaluate(_make_features(blockers=[blocker]))
    assert result.global_score <= 2.0
    assert result.blocker_gate_active is True


def test_blocker_severity_exactly_at_medium_boundary():
    """Severity 1.6 (== medium_max_severity) should cap at medium_cap=3.0."""
    blocker = Blocker(type="geographic", description="Must be in EU", severity=1.6)
    result = evaluate(_make_features(blockers=[blocker]))
    assert result.global_score <= 3.0
    assert result.blocker_gate_active is True


def test_multiple_blockers_uses_min_severity():
    """With multiple blockers, the min severity drives the gate tier."""
    blockers = [
        Blocker(type="citizenship", description="US only", severity=1.0),
        Blocker(type="domain", description="Needs clearance", severity=1.8),
    ]
    result = evaluate(_make_features(blockers=blockers))
    # min severity = 1.0 => hard cap at 2.0
    assert result.global_score <= 2.0
    assert result.blocker_gate_active is True


def test_no_blockers_means_gate_inactive():
    """No blockers should leave the gate inactive."""
    result = evaluate(_make_features(blockers=[]))
    assert result.blocker_gate_active is False
    assert result.blocker_gate_reason is None


###############################################################################
# scoring.engine.evaluate -- full pipeline integration
###############################################################################


def test_evaluate_returns_score_result_with_all_fields():
    result = evaluate(_make_features())
    assert hasattr(result, "dimensions")
    assert hasattr(result, "global_score")
    assert hasattr(result, "blocker_gate_active")
    assert hasattr(result, "interpretation")
    assert hasattr(result, "score_table")
    assert hasattr(result, "warnings")
    assert hasattr(result, "diagnostic_trace")


def test_evaluate_dimensions_has_six_entries():
    result = evaluate(_make_features())
    assert len(result.dimensions) == 6


def test_evaluate_global_score_is_bounded():
    result = evaluate(_make_features())
    assert 1.0 <= result.global_score <= 5.0


def test_evaluate_accepts_custom_config():
    custom_config = ScoreConfig(
        comp_thresholds=CompThresholds(band_4_min=0.90, band_3_min=0.75),
        blocker_gate=BlockerGate(),
    )
    result = evaluate(_make_features(), config=custom_config)
    assert 1.0 <= result.global_score <= 5.0


def test_evaluate_custom_comp_thresholds_change_score():
    """Tighter comp thresholds should lower the comp score for borderline ratios."""
    # Default: band_4_min=0.86. With salary 220K / target 250K = 0.88 => score 4.0
    # Custom: band_4_min=0.90. 0.88 < 0.90 => score 3.0
    features = _make_features(salary_low=220000, salary_high=220000)

    result_default = evaluate(features)
    result_strict = evaluate(features, config=ScoreConfig(
        comp_thresholds=CompThresholds(band_4_min=0.90),
    ))

    default_comp = next(d for d in result_default.dimensions if d.name == "Comp Alignment")
    strict_comp = next(d for d in result_strict.dimensions if d.name == "Comp Alignment")

    assert default_comp.score == 4.0
    assert strict_comp.score == 3.0


def test_evaluate_normalization_dampening_lowers_cv_match():
    """When dampening fires, CV Match score should be lower than undampened."""
    # 4 reqs all at 0.95 => mean 0.95 > 0.85 => dampened to 0.95 * 0.90 = 0.855
    high_reqs = [
        Requirement(text=f"Skill {i}", priority="must", match_strength=0.95, evidence="yes")
        for i in range(5)
    ]
    # 2 reqs won't trigger dampening
    low_count_reqs = [
        Requirement(text="Python", priority="must", match_strength=0.95, evidence="yes"),
        Requirement(text="SQL", priority="must", match_strength=0.95, evidence="yes"),
    ]

    result_dampened = evaluate(_make_features(requirements=high_reqs))
    result_undampened = evaluate(_make_features(requirements=low_count_reqs))

    dampened_cv = next(d for d in result_dampened.dimensions if d.name == "CV Match")
    undampened_cv = next(d for d in result_undampened.dimensions if d.name == "CV Match")

    assert dampened_cv.score < undampened_cv.score
