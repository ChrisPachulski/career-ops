from __future__ import annotations

import pytest

from scoring.models import Blocker, JDFeatures, OrgSignals, Requirement, Warning
from scoring.validate import validate_features, validate_scores


###############################################################################
# Helpers -- build minimal valid JDFeatures with targeted overrides
###############################################################################


def make_requirement(**overrides) -> dict:
    base = {
        "text": "5 years Python",
        "priority": "must",
        "match_strength": 0.8,
        "evidence": "Used Python for 6 years",
    }
    base.update(overrides)
    return base


def make_org_signals(**overrides) -> dict:
    base = {
        "org_stability": 4.0,
        "remote_policy": "remote",
        "location_fit": 5.0,
    }
    base.update(overrides)
    return base


def make_features(**overrides) -> JDFeatures:
    base: dict = {
        "comp_target": 250000.0,
        "jd_seniority": "staff",
        "candidate_seniority": "staff",
        "detected_archetype": "analytics-engineer",
        "target_archetypes": ["analytics-engineer", "data-engineer"],
        "archetype_adjacency": 1.0,
        "requirements": [make_requirement(match_strength=0.9)],
        "org_signals": make_org_signals(),
        "blockers": [],
    }
    base.update(overrides)
    return JDFeatures(**base)


def _codes(warnings: list[Warning]) -> list[str]:
    """Extract warning codes for easy assertion."""
    return [w.code for w in warnings]


###############################################################################
# validate_features -- clean features produce no warnings
###############################################################################


def test_returns_empty_when_no_issues():
    features = make_features()
    result = validate_features(features)
    assert result == []


def test_returns_empty_when_salary_range_is_valid():
    features = make_features(salary_low=180000.0, salary_high=220000.0)
    result = validate_features(features)
    assert result == []


def test_returns_empty_when_requirements_have_varied_match_strength():
    features = make_features(requirements=[
        make_requirement(match_strength=0.9),
        make_requirement(match_strength=0.6),
        make_requirement(match_strength=0.3),
    ])
    result = validate_features(features)
    assert result == []


def test_returns_empty_when_archetype_is_exact_match_with_adjacency_1():
    features = make_features(
        detected_archetype="analytics-engineer",
        target_archetypes=["analytics-engineer"],
        archetype_adjacency=1.0,
    )
    result = validate_features(features)
    assert result == []


def test_returns_empty_when_salary_equal_but_midpoint_present():
    features = make_features(
        salary_low=200000.0,
        salary_high=200000.0,
        salary_midpoint=200000.0,
    )
    result = validate_features(features)
    assert result == []


###############################################################################
# validate_features -- SALARY_INVERTED
###############################################################################


def test_salary_inverted_fires_when_low_exceeds_high():
    features = make_features(salary_low=250000.0, salary_high=180000.0)
    result = validate_features(features)
    assert "SALARY_INVERTED" in _codes(result)


def test_salary_inverted_does_not_fire_when_equal():
    features = make_features(salary_low=200000.0, salary_high=200000.0)
    result = validate_features(features)
    assert "SALARY_INVERTED" not in _codes(result)


def test_salary_inverted_does_not_fire_when_one_bound_is_none():
    features = make_features(salary_low=250000.0, salary_high=None)
    result = validate_features(features)
    assert "SALARY_INVERTED" not in _codes(result)


def test_salary_inverted_warning_has_correct_tier():
    features = make_features(salary_low=300000.0, salary_high=100000.0)
    result = validate_features(features)
    inverted = [w for w in result if w.code == "SALARY_INVERTED"]
    assert len(inverted) == 1
    assert inverted[0].tier == "pre_computation"


###############################################################################
# validate_features -- UNIFORM_MATCH_STRENGTH
###############################################################################


def test_uniform_match_strength_fires_with_3_identical_requirements():
    features = make_features(requirements=[
        make_requirement(match_strength=0.7),
        make_requirement(match_strength=0.7),
        make_requirement(match_strength=0.7),
    ])
    result = validate_features(features)
    assert "UNIFORM_MATCH_STRENGTH" in _codes(result)


def test_uniform_match_strength_fires_with_5_identical_requirements():
    features = make_features(requirements=[
        make_requirement(match_strength=1.0) for _ in range(5)
    ])
    result = validate_features(features)
    assert "UNIFORM_MATCH_STRENGTH" in _codes(result)


def test_uniform_match_strength_does_not_fire_with_2_identical_requirements():
    features = make_features(requirements=[
        make_requirement(match_strength=0.7),
        make_requirement(match_strength=0.7),
    ])
    result = validate_features(features)
    assert "UNIFORM_MATCH_STRENGTH" not in _codes(result)


def test_uniform_match_strength_does_not_fire_when_one_differs():
    features = make_features(requirements=[
        make_requirement(match_strength=0.7),
        make_requirement(match_strength=0.7),
        make_requirement(match_strength=0.8),
    ])
    result = validate_features(features)
    assert "UNIFORM_MATCH_STRENGTH" not in _codes(result)


def test_uniform_match_strength_does_not_fire_with_empty_requirements():
    features = make_features(requirements=[])
    result = validate_features(features)
    assert "UNIFORM_MATCH_STRENGTH" not in _codes(result)


###############################################################################
# validate_features -- ADJACENCY_WITH_EXACT_MATCH
###############################################################################


def test_adjacency_fires_when_archetype_in_targets_but_adjacency_below_1():
    features = make_features(
        detected_archetype="analytics-engineer",
        target_archetypes=["analytics-engineer", "data-engineer"],
        archetype_adjacency=0.8,
    )
    result = validate_features(features)
    assert "ADJACENCY_WITH_EXACT_MATCH" in _codes(result)


def test_adjacency_does_not_fire_when_archetype_not_in_targets():
    features = make_features(
        detected_archetype="ml-engineer",
        target_archetypes=["analytics-engineer", "data-engineer"],
        archetype_adjacency=0.6,
    )
    result = validate_features(features)
    assert "ADJACENCY_WITH_EXACT_MATCH" not in _codes(result)


def test_adjacency_does_not_fire_when_adjacency_is_1():
    features = make_features(
        detected_archetype="analytics-engineer",
        target_archetypes=["analytics-engineer"],
        archetype_adjacency=1.0,
    )
    result = validate_features(features)
    assert "ADJACENCY_WITH_EXACT_MATCH" not in _codes(result)


def test_adjacency_fires_at_boundary_just_below_1():
    features = make_features(
        detected_archetype="data-engineer",
        target_archetypes=["data-engineer"],
        archetype_adjacency=0.99,
    )
    result = validate_features(features)
    assert "ADJACENCY_WITH_EXACT_MATCH" in _codes(result)


###############################################################################
# validate_features -- SALARY_POINT_ESTIMATE
###############################################################################


def test_salary_point_estimate_fires_when_bounds_equal_and_no_midpoint():
    features = make_features(
        salary_low=200000.0,
        salary_high=200000.0,
        salary_midpoint=None,
    )
    result = validate_features(features)
    assert "SALARY_POINT_ESTIMATE" in _codes(result)


def test_salary_point_estimate_does_not_fire_when_bounds_differ():
    features = make_features(
        salary_low=180000.0,
        salary_high=220000.0,
        salary_midpoint=None,
    )
    result = validate_features(features)
    assert "SALARY_POINT_ESTIMATE" not in _codes(result)


def test_salary_point_estimate_does_not_fire_when_midpoint_present():
    features = make_features(
        salary_low=200000.0,
        salary_high=200000.0,
        salary_midpoint=200000.0,
    )
    result = validate_features(features)
    assert "SALARY_POINT_ESTIMATE" not in _codes(result)


def test_salary_point_estimate_does_not_fire_when_salary_is_none():
    features = make_features(salary_low=None, salary_high=None)
    result = validate_features(features)
    assert "SALARY_POINT_ESTIMATE" not in _codes(result)


###############################################################################
# validate_features -- multiple warnings can co-exist
###############################################################################


def test_multiple_warnings_fire_simultaneously():
    features = make_features(
        salary_low=250000.0,
        salary_high=180000.0,
        requirements=[
            make_requirement(match_strength=0.5),
            make_requirement(match_strength=0.5),
            make_requirement(match_strength=0.5),
        ],
        detected_archetype="analytics-engineer",
        target_archetypes=["analytics-engineer"],
        archetype_adjacency=0.7,
    )
    result = validate_features(features)
    codes = _codes(result)
    assert "SALARY_INVERTED" in codes
    assert "UNIFORM_MATCH_STRENGTH" in codes
    assert "ADJACENCY_WITH_EXACT_MATCH" in codes


###############################################################################
# validate_scores -- clean scores produce no warnings
###############################################################################


def _standard_dim_scores(**overrides) -> dict[str, float]:
    """Return well-separated dimension scores that trigger nothing."""
    base = {
        "CV Match": 3.8,
        "Archetype Fit": 4.2,
        "Comp Alignment": 3.5,
        "Level Fit": 4.0,
        "Org Risk": 3.0,
        "Blockers": 4.5,
    }
    base.update(overrides)
    return base


def test_validate_scores_returns_empty_when_no_issues():
    features = make_features()
    result = validate_scores(_standard_dim_scores(), features)
    assert result == []


###############################################################################
# validate_scores -- UNIFORM_SCORES
###############################################################################


def test_uniform_scores_fires_when_all_within_half_point():
    dim_scores = {
        "CV Match": 3.5,
        "Archetype Fit": 3.6,
        "Comp Alignment": 3.7,
        "Level Fit": 3.4,
        "Org Risk": 3.3,
        "Blockers": 3.6,
    }
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "UNIFORM_SCORES" in _codes(result)


def test_uniform_scores_fires_when_all_identical():
    dim_scores = {k: 4.0 for k in [
        "CV Match", "Archetype Fit", "Comp Alignment",
        "Level Fit", "Org Risk", "Blockers",
    ]}
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "UNIFORM_SCORES" in _codes(result)


def test_uniform_scores_does_not_fire_when_spread_is_0_5():
    dim_scores = {
        "CV Match": 3.0,
        "Archetype Fit": 3.5,
        "Comp Alignment": 3.2,
        "Level Fit": 3.1,
        "Org Risk": 3.3,
        "Blockers": 3.4,
    }
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "UNIFORM_SCORES" not in _codes(result)


def test_uniform_scores_does_not_fire_when_spread_exceeds_0_5():
    dim_scores = {
        "CV Match": 2.0,
        "Archetype Fit": 4.5,
        "Comp Alignment": 3.0,
        "Level Fit": 3.5,
        "Org Risk": 4.0,
        "Blockers": 3.0,
    }
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "UNIFORM_SCORES" not in _codes(result)


def test_uniform_scores_has_correct_tier():
    dim_scores = {k: 3.5 for k in [
        "CV Match", "Archetype Fit", "Comp Alignment",
        "Level Fit", "Org Risk", "Blockers",
    ]}
    features = make_features()
    result = validate_scores(dim_scores, features)
    uniform = [w for w in result if w.code == "UNIFORM_SCORES"]
    assert len(uniform) == 1
    assert uniform[0].tier == "post_computation"


###############################################################################
# validate_scores -- MATCH_BLOCKER_CONTRADICTION
###############################################################################


def test_match_blocker_contradiction_fires_when_cv_high_and_blockers_low():
    dim_scores = _standard_dim_scores(**{"CV Match": 4.5, "Blockers": 2.0})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" in _codes(result)


def test_match_blocker_contradiction_fires_at_extreme_values():
    dim_scores = _standard_dim_scores(**{"CV Match": 5.0, "Blockers": 1.0})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" in _codes(result)


def test_match_blocker_contradiction_does_not_fire_when_cv_below_threshold():
    dim_scores = _standard_dim_scores(**{"CV Match": 4.4, "Blockers": 2.0})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" not in _codes(result)


def test_match_blocker_contradiction_does_not_fire_when_blockers_above_threshold():
    dim_scores = _standard_dim_scores(**{"CV Match": 4.5, "Blockers": 2.1})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" not in _codes(result)


def test_match_blocker_contradiction_does_not_fire_when_cv_match_key_missing():
    dim_scores = _standard_dim_scores()
    del dim_scores["CV Match"]
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" not in _codes(result)


###############################################################################
# validate_scores -- COMP_LEVEL_MISMATCH
###############################################################################


def test_comp_level_mismatch_fires_when_comp_high_and_level_low():
    dim_scores = _standard_dim_scores(**{"Comp Alignment": 5.0, "Level Fit": 2.5})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" in _codes(result)


def test_comp_level_mismatch_fires_at_extreme_values():
    dim_scores = _standard_dim_scores(**{"Comp Alignment": 5.0, "Level Fit": 1.0})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" in _codes(result)


def test_comp_level_mismatch_does_not_fire_when_comp_below_5():
    dim_scores = _standard_dim_scores(**{"Comp Alignment": 4.9, "Level Fit": 2.5})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" not in _codes(result)


def test_comp_level_mismatch_does_not_fire_when_level_above_threshold():
    dim_scores = _standard_dim_scores(**{"Comp Alignment": 5.0, "Level Fit": 2.6})
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" not in _codes(result)


def test_comp_level_mismatch_does_not_fire_when_comp_key_missing():
    dim_scores = _standard_dim_scores()
    del dim_scores["Comp Alignment"]
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" not in _codes(result)


###############################################################################
# validate_scores -- multiple warnings can co-exist
###############################################################################


def test_validate_scores_multiple_warnings_fire_simultaneously():
    dim_scores = {
        "CV Match": 4.8,
        "Archetype Fit": 4.8,
        "Comp Alignment": 5.0,
        "Level Fit": 2.0,
        "Org Risk": 4.8,
        "Blockers": 1.5,
    }
    features = make_features()
    result = validate_scores(dim_scores, features)
    codes = _codes(result)
    assert "MATCH_BLOCKER_CONTRADICTION" in codes
    assert "COMP_LEVEL_MISMATCH" in codes


###############################################################################
# validate_scores -- default value behavior when keys are missing
###############################################################################


def test_validate_scores_uses_default_0_for_missing_cv_match():
    """Missing CV Match defaults to 0.0, so contradiction cannot fire."""
    dim_scores = {"Blockers": 1.0, "Comp Alignment": 3.0, "Level Fit": 3.0}
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" not in _codes(result)


def test_validate_scores_uses_default_5_for_missing_blockers():
    """Missing Blockers defaults to 5.0, so contradiction cannot fire."""
    dim_scores = {"CV Match": 5.0, "Comp Alignment": 3.0, "Level Fit": 3.0}
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "MATCH_BLOCKER_CONTRADICTION" not in _codes(result)


def test_validate_scores_uses_default_3_for_missing_comp():
    """Missing Comp Alignment defaults to 3.0, so mismatch cannot fire."""
    dim_scores = {"CV Match": 3.0, "Level Fit": 1.0, "Blockers": 4.0}
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" not in _codes(result)


def test_validate_scores_uses_default_3_for_missing_level_fit():
    """Missing Level Fit defaults to 3.0, so mismatch cannot fire."""
    dim_scores = {"CV Match": 3.0, "Comp Alignment": 5.0, "Blockers": 4.0}
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert "COMP_LEVEL_MISMATCH" not in _codes(result)


###############################################################################
# Warning structure
###############################################################################


def test_all_pre_computation_warnings_have_correct_tier():
    features = make_features(
        salary_low=250000.0,
        salary_high=180000.0,
        requirements=[
            make_requirement(match_strength=0.5),
            make_requirement(match_strength=0.5),
            make_requirement(match_strength=0.5),
        ],
        detected_archetype="analytics-engineer",
        target_archetypes=["analytics-engineer"],
        archetype_adjacency=0.7,
    )
    result = validate_features(features)
    assert len(result) >= 3
    for w in result:
        assert w.tier == "pre_computation"


def test_all_post_computation_warnings_have_correct_tier():
    dim_scores = {
        "CV Match": 4.8,
        "Archetype Fit": 4.8,
        "Comp Alignment": 5.0,
        "Level Fit": 2.0,
        "Org Risk": 4.8,
        "Blockers": 1.5,
    }
    features = make_features()
    result = validate_scores(dim_scores, features)
    assert len(result) >= 2
    for w in result:
        assert w.tier == "post_computation"


def test_warning_message_is_nonempty_string():
    features = make_features(salary_low=300000.0, salary_high=100000.0)
    result = validate_features(features)
    assert len(result) == 1
    assert isinstance(result[0].message, str)
    assert len(result[0].message) > 0
