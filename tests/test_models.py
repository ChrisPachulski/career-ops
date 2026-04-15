from __future__ import annotations

import pytest
from pydantic import ValidationError

from scoring.models import Blocker, DimensionScore, JDFeatures, OrgSignals, Requirement, ScoreResult


###############################################################################
# Requirement
###############################################################################


def make_requirement(**overrides):
    base = {
        "text": "5 years Python",
        "priority": "must",
        "match_strength": 0.8,
        "evidence": "Used Python for 6 years",
    }
    base.update(overrides)
    return base


def test_requirement_accepts_valid_data():
    r = Requirement(**make_requirement())
    assert r.text == "5 years Python"
    assert r.priority == "must"
    assert r.match_strength == 0.8


def test_requirement_accepts_all_priority_values():
    for priority in ("must", "preferred", "nice"):
        r = Requirement(**make_requirement(priority=priority))
        assert r.priority == priority


def test_requirement_rejects_invalid_priority():
    with pytest.raises(ValidationError):
        Requirement(**make_requirement(priority="optional"))


def test_requirement_rejects_match_strength_above_1():
    with pytest.raises(ValidationError):
        Requirement(**make_requirement(match_strength=1.1))


def test_requirement_rejects_match_strength_below_0():
    with pytest.raises(ValidationError):
        Requirement(**make_requirement(match_strength=-0.1))


def test_requirement_accepts_match_strength_boundary_values():
    Requirement(**make_requirement(match_strength=0.0))
    Requirement(**make_requirement(match_strength=1.0))


###############################################################################
# OrgSignals
###############################################################################


def make_org_signals(**overrides):
    base = {
        "glassdoor_rating": 4.2,
        "recent_layoffs": False,
        "org_stability": 3.5,
        "remote_policy": "remote",
        "location_fit": 5.0,
    }
    base.update(overrides)
    return base


def test_org_signals_accepts_full_data():
    o = OrgSignals(**make_org_signals())
    assert o.glassdoor_rating == 4.2
    assert o.recent_layoffs is False


def test_org_signals_accepts_minimal_data():
    o = OrgSignals(org_stability=3.0, remote_policy="hybrid", location_fit=4.0)
    assert o.glassdoor_rating is None
    assert o.recent_layoffs is None


def test_org_signals_rejects_invalid_remote_policy():
    with pytest.raises(ValidationError):
        OrgSignals(**make_org_signals(remote_policy="flexible"))


def test_org_signals_accepts_all_remote_policy_values():
    for policy in ("remote", "hybrid", "onsite", "unknown"):
        o = OrgSignals(**make_org_signals(remote_policy=policy))
        assert o.remote_policy == policy


###############################################################################
# Blocker
###############################################################################


def make_blocker(**overrides):
    base = {
        "type": "credentials",
        "description": "Requires CISSP certification",
        "severity": 1.5,
    }
    base.update(overrides)
    return base


def test_blocker_accepts_valid_data():
    b = Blocker(**make_blocker())
    assert b.type == "credentials"
    assert b.severity == 1.5


def test_blocker_accepts_all_type_values():
    for t in ("credentials", "citizenship", "experience_years", "domain", "geographic"):
        b = Blocker(**make_blocker(type=t))
        assert b.type == t


def test_blocker_rejects_invalid_type():
    with pytest.raises(ValidationError):
        Blocker(**make_blocker(type="language"))


def test_blocker_rejects_severity_above_2():
    with pytest.raises(ValidationError):
        Blocker(**make_blocker(severity=2.1))


def test_blocker_rejects_severity_below_1():
    with pytest.raises(ValidationError):
        Blocker(**make_blocker(severity=0.9))


def test_blocker_accepts_severity_boundary_values():
    Blocker(**make_blocker(severity=1.0))
    Blocker(**make_blocker(severity=2.0))


###############################################################################
# JDFeatures
###############################################################################


def make_jd_features(**overrides):
    base = {
        "comp_target": 250000.0,
        "jd_seniority": "staff",
        "candidate_seniority": "staff",
        "detected_archetype": "analytics-engineer",
        "target_archetypes": ["analytics-engineer", "data-engineer"],
        "archetype_adjacency": 1.0,
        "requirements": [
            {
                "text": "5 years Python",
                "priority": "must",
                "match_strength": 0.9,
                "evidence": "6 years Python",
            }
        ],
        "org_signals": {
            "org_stability": 4.0,
            "remote_policy": "remote",
            "location_fit": 5.0,
        },
        "blockers": [],
    }
    base.update(overrides)
    return base


def test_jd_features_accepts_minimal_valid_data():
    jd = JDFeatures(**make_jd_features())
    assert jd.comp_target == 250000.0
    assert jd.jd_seniority == "staff"
    assert jd.salary_low is None
    assert jd.salary_high is None
    assert jd.salary_midpoint is None


def test_jd_features_rejects_invalid_jd_seniority():
    with pytest.raises(ValidationError):
        JDFeatures(**make_jd_features(jd_seniority="lead"))


def test_jd_features_rejects_invalid_candidate_seniority():
    with pytest.raises(ValidationError):
        JDFeatures(**make_jd_features(candidate_seniority="associate"))


def test_jd_features_accepts_all_seniority_values():
    for level in ("junior", "mid", "senior", "staff", "principal", "director", "vp"):
        jd = JDFeatures(**make_jd_features(jd_seniority=level, candidate_seniority=level))
        assert jd.jd_seniority == level


def test_jd_features_accepts_salary_fields():
    jd = JDFeatures(**make_jd_features(salary_low=180000.0, salary_high=220000.0, salary_midpoint=200000.0))
    assert jd.salary_low == 180000.0
    assert jd.salary_high == 220000.0
    assert jd.salary_midpoint == 200000.0


###############################################################################
# ScoreResult
###############################################################################


def make_score_result(**overrides):
    base = {
        "dimensions": [
            {
                "name": "comp_alignment",
                "score": 4.0,
                "weight": 0.25,
                "weighted": 1.0,
                "reasoning": "Salary near target",
            }
        ],
        "global_score": 4.0,
        "blocker_gate_active": False,
        "blocker_gate_reason": None,
        "interpretation": "Strong match",
        "score_table": "| dim | score |\n|-----|-------|\n| comp | 4.0 |",
    }
    base.update(overrides)
    return base


def test_score_result_accepts_valid_data():
    sr = ScoreResult(**make_score_result())
    assert sr.global_score == 4.0
    assert sr.blocker_gate_active is False
    assert len(sr.dimensions) == 1


def test_score_result_accepts_blocker_gate_active_with_reason():
    sr = ScoreResult(**make_score_result(blocker_gate_active=True, blocker_gate_reason="Requires US citizenship"))
    assert sr.blocker_gate_active is True
    assert sr.blocker_gate_reason == "Requires US citizenship"


def test_score_result_rejects_global_score_below_1():
    with pytest.raises(ValidationError):
        ScoreResult(**make_score_result(global_score=0.5))


def test_score_result_rejects_global_score_above_5():
    with pytest.raises(ValidationError):
        ScoreResult(**make_score_result(global_score=5.5))
