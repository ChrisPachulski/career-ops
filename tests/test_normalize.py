from __future__ import annotations

import pytest

from scoring.models import JDFeatures, OrgSignals, Requirement, Warning
from scoring.normalize import (
    _DAMPENING_MEAN_THRESHOLD,
    _DAMPENING_MIN_REQUIREMENTS,
    _MATCH_STRENGTH_DAMPENING,
    normalize_features,
)


###############################################################################
# Helpers
###############################################################################


def make_requirement(match_strength: float = 0.9, **overrides) -> Requirement:
    base = {
        "text": "5 years Python",
        "priority": "must",
        "match_strength": match_strength,
        "evidence": "6 years Python experience",
    }
    base.update(overrides)
    return Requirement(**base)


def make_org_signals(**overrides) -> OrgSignals:
    base = {
        "org_stability": 4.0,
        "remote_policy": "remote",
        "location_fit": 5.0,
    }
    base.update(overrides)
    return OrgSignals(**base)


_SENTINEL = object()


def make_features(
    requirements: list[Requirement] | object = _SENTINEL,
    **overrides,
) -> JDFeatures:
    if requirements is _SENTINEL:
        reqs = [make_requirement()]
    else:
        reqs = requirements
    base = {
        "comp_target": 250000.0,
        "jd_seniority": "staff",
        "candidate_seniority": "staff",
        "detected_archetype": "analytics-engineer",
        "target_archetypes": ["analytics-engineer", "data-engineer"],
        "archetype_adjacency": 1.0,
        "requirements": reqs,
        "org_signals": make_org_signals(),
        "blockers": [],
    }
    base.update(overrides)
    return JDFeatures(**base)


###############################################################################
# Dampening fires -- high mean, enough requirements
###############################################################################


def test_dampening_fires_when_mean_above_threshold_and_enough_reqs():
    reqs = [make_requirement(match_strength=0.95) for _ in range(5)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert len(warnings) == 1
    assert warnings[0].code == "MATCH_STRENGTH_DAMPENED"
    for r in result.requirements:
        assert r.match_strength == round(0.95 * _MATCH_STRENGTH_DAMPENING, 2)


def test_dampening_returns_pre_computation_tier_warning():
    reqs = [make_requirement(match_strength=0.90) for _ in range(4)]
    features = make_features(requirements=reqs)

    _, warnings = normalize_features(features)

    assert warnings[0].tier == "pre_computation"


def test_dampening_warning_message_includes_mean_and_factor():
    reqs = [make_requirement(match_strength=0.90) for _ in range(4)]
    features = make_features(requirements=reqs)

    _, warnings = normalize_features(features)

    assert "0.90" in warnings[0].message
    assert str(_MATCH_STRENGTH_DAMPENING) in warnings[0].message


def test_dampening_applies_per_requirement_not_uniform():
    reqs = [
        make_requirement(match_strength=0.90),
        make_requirement(match_strength=0.95),
        make_requirement(match_strength=1.00),
        make_requirement(match_strength=0.86),
    ]
    features = make_features(requirements=reqs)
    # mean = (0.90 + 0.95 + 1.00 + 0.86) / 4 = 0.9275 > 0.85

    result, warnings = normalize_features(features)

    assert len(warnings) == 1
    expected = [
        round(0.90 * _MATCH_STRENGTH_DAMPENING, 2),
        round(0.95 * _MATCH_STRENGTH_DAMPENING, 2),
        round(1.00 * _MATCH_STRENGTH_DAMPENING, 2),
        round(0.86 * _MATCH_STRENGTH_DAMPENING, 2),
    ]
    actual = [r.match_strength for r in result.requirements]
    assert actual == expected


###############################################################################
# Dampening does NOT fire -- below threshold
###############################################################################


def test_no_dampening_when_mean_at_threshold():
    # Mean exactly 0.85 -- condition is strictly >, so no dampening
    reqs = [make_requirement(match_strength=0.85) for _ in range(4)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert warnings == []
    for orig, res in zip(features.requirements, result.requirements):
        assert orig.match_strength == res.match_strength


def test_no_dampening_when_mean_below_threshold():
    reqs = [make_requirement(match_strength=0.70) for _ in range(5)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert warnings == []
    for r in result.requirements:
        assert r.match_strength == 0.70


###############################################################################
# Dampening does NOT fire -- too few requirements
###############################################################################


def test_no_dampening_with_three_high_strength_requirements():
    reqs = [make_requirement(match_strength=0.95) for _ in range(3)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert warnings == []
    for r in result.requirements:
        assert r.match_strength == 0.95


def test_no_dampening_with_one_requirement():
    reqs = [make_requirement(match_strength=1.0)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert warnings == []
    assert result.requirements[0].match_strength == 1.0


def test_no_dampening_with_zero_requirements():
    features = make_features(requirements=[])

    result, warnings = normalize_features(features)

    assert warnings == []
    assert result.requirements == []


###############################################################################
# Boundary cases -- exactly at thresholds
###############################################################################


def test_exactly_four_reqs_at_exactly_threshold_no_dampening():
    """4 reqs (meets min) but mean == 0.85 (not strictly >). No dampening."""
    reqs = [make_requirement(match_strength=0.85) for _ in range(4)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert warnings == []
    assert [r.match_strength for r in result.requirements] == [0.85] * 4


def test_exactly_four_reqs_just_above_threshold_dampens():
    """4 reqs at mean 0.8501 -- just above threshold, dampening fires."""
    # Use 4 reqs: three at 0.85 and one at 0.8504 -> mean = 0.8501
    reqs = [
        make_requirement(match_strength=0.85),
        make_requirement(match_strength=0.85),
        make_requirement(match_strength=0.85),
        make_requirement(match_strength=0.86),
    ]
    features = make_features(requirements=reqs)
    # mean = (0.85 + 0.85 + 0.85 + 0.86) / 4 = 0.8525 > 0.85

    result, warnings = normalize_features(features)

    assert len(warnings) == 1
    assert warnings[0].code == "MATCH_STRENGTH_DAMPENED"


def test_three_reqs_above_threshold_no_dampening():
    """3 reqs (below min count) with high mean. No dampening."""
    reqs = [make_requirement(match_strength=1.0) for _ in range(3)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    assert warnings == []


@pytest.mark.parametrize(
    "n_reqs, strength, should_dampen",
    [
        (3, 0.95, False),   # too few reqs
        (4, 0.80, False),   # mean too low
        (4, 0.85, False),   # mean at threshold (not strictly >)
        (4, 0.86, True),    # exactly at min reqs, above threshold
        (5, 0.90, True),    # above both thresholds
        (10, 0.95, True),   # many reqs, high mean
    ],
    ids=[
        "3_reqs_high_mean",
        "4_reqs_low_mean",
        "4_reqs_at_threshold",
        "4_reqs_above_threshold",
        "5_reqs_above_threshold",
        "10_reqs_high_mean",
    ],
)
def test_dampening_parametrized(n_reqs: int, strength: float, should_dampen: bool):
    reqs = [make_requirement(match_strength=strength) for _ in range(n_reqs)]
    features = make_features(requirements=reqs)

    result, warnings = normalize_features(features)

    if should_dampen:
        assert len(warnings) == 1
        assert warnings[0].code == "MATCH_STRENGTH_DAMPENED"
        for r in result.requirements:
            assert r.match_strength == round(strength * _MATCH_STRENGTH_DAMPENING, 2)
    else:
        assert warnings == []
        for r in result.requirements:
            assert r.match_strength == strength


###############################################################################
# Immutability -- input is never mutated
###############################################################################


def test_input_features_unchanged_after_dampening():
    reqs = [make_requirement(match_strength=0.95) for _ in range(5)]
    features = make_features(requirements=reqs)
    original_strengths = [r.match_strength for r in features.requirements]

    result, _ = normalize_features(features)

    # Input object must be untouched
    after_strengths = [r.match_strength for r in features.requirements]
    assert after_strengths == original_strengths
    assert after_strengths == [0.95] * 5

    # Result must be a different object
    assert result is not features
    assert result.requirements is not features.requirements


def test_input_features_unchanged_when_no_dampening():
    reqs = [make_requirement(match_strength=0.70) for _ in range(2)]
    features = make_features(requirements=reqs)
    original_strengths = [r.match_strength for r in features.requirements]

    result, _ = normalize_features(features)

    after_strengths = [r.match_strength for r in features.requirements]
    assert after_strengths == original_strengths


def test_non_requirement_fields_preserved_after_dampening():
    reqs = [make_requirement(match_strength=0.95) for _ in range(5)]
    features = make_features(
        requirements=reqs,
        salary_low=180000.0,
        salary_high=220000.0,
        salary_midpoint=200000.0,
    )

    result, _ = normalize_features(features)

    assert result.salary_low == features.salary_low
    assert result.salary_high == features.salary_high
    assert result.salary_midpoint == features.salary_midpoint
    assert result.comp_target == features.comp_target
    assert result.jd_seniority == features.jd_seniority
    assert result.detected_archetype == features.detected_archetype
    assert result.org_signals == features.org_signals
    assert result.blockers == features.blockers


###############################################################################
# Constants sanity checks
###############################################################################


def test_module_constants_have_expected_values():
    assert _MATCH_STRENGTH_DAMPENING == 0.90
    assert _DAMPENING_MEAN_THRESHOLD == 0.85
    assert _DAMPENING_MIN_REQUIREMENTS == 4
