from __future__ import annotations

import pytest

from scoring.engine import (
    compute_global,
    score_archetype_fit,
    score_blockers,
    score_comp_alignment,
    score_cv_match,
    score_level_fit,
    score_org_risk,
)
from scoring.models import Blocker, JDFeatures, OrgSignals, Requirement


###############################################################################
# score_comp_alignment
###############################################################################


class TestScoreCompAlignment:
    def test_at_target_returns_5(self):
        assert score_comp_alignment(250000.0, 250000.0, 250000.0) == 5.0

    def test_above_target_returns_5(self):
        assert score_comp_alignment(270000.0, 310000.0, 250000.0) == 5.0

    def test_one_to_fourteen_percent_below_returns_4(self):
        # 14% below: 250000 * 0.86 = 215000, just above that is 216000
        assert score_comp_alignment(200000.0, 232000.0, 250000.0) == 4.0

    def test_fifteen_to_29_percent_below_returns_3(self):
        # 20% below target: effective = 200000, ratio = 0.80
        assert score_comp_alignment(190000.0, 210000.0, 250000.0) == 3.0

    def test_thirty_percent_below_returns_2(self):
        # 35% below: effective = 162500, ratio = 0.65
        assert score_comp_alignment(150000.0, 175000.0, 250000.0) == 2.0

    def test_no_salary_info_returns_3(self):
        assert score_comp_alignment(None, None, 250000.0) == 3.0

    def test_only_low_bound_uses_low(self):
        # low = 250000 = target => ratio 1.0 => 5.0
        assert score_comp_alignment(250000.0, None, 250000.0) == 5.0

    def test_only_low_bound_below_target(self):
        # low = 200000, target = 250000 => ratio 0.80 => 3.0
        assert score_comp_alignment(200000.0, None, 250000.0) == 3.0

    def test_only_high_bound_uses_high(self):
        # high = 250000 = target => ratio 1.0 => 5.0
        assert score_comp_alignment(None, 250000.0, 250000.0) == 5.0

    def test_only_high_bound_below_target(self):
        # high = 160000, target = 250000 => ratio 0.64 => 2.0
        assert score_comp_alignment(None, 160000.0, 250000.0) == 2.0

    def test_explicit_midpoint_takes_precedence_over_range(self):
        # midpoint = 250000 but low/high average would be different
        assert score_comp_alignment(100000.0, 150000.0, 250000.0, salary_midpoint=250000.0) == 5.0

    def test_explicit_midpoint_below_target(self):
        # midpoint = 160000, target = 250000 => ratio 0.64 => 2.0
        assert score_comp_alignment(None, None, 250000.0, salary_midpoint=160000.0) == 2.0

    # Boundary tests
    def test_boundary_exactly_86_percent_returns_4(self):
        # effective = 215000, target = 250000 => ratio = 0.86 exactly
        assert score_comp_alignment(215000.0, 215000.0, 250000.0) == 4.0

    def test_boundary_just_below_86_percent_returns_3(self):
        # effective = 214999, target = 250000 => ratio = 0.859996 < 0.86
        assert score_comp_alignment(214999.0, 214999.0, 250000.0) == 3.0

    def test_boundary_exactly_71_percent_returns_3(self):
        # effective = 177500, target = 250000 => ratio = 0.71 exactly
        assert score_comp_alignment(177500.0, 177500.0, 250000.0) == 3.0

    def test_boundary_just_below_71_percent_returns_2(self):
        # effective = 177499, target = 250000 => ratio = 0.709996 < 0.71
        assert score_comp_alignment(177499.0, 177499.0, 250000.0) == 2.0


###############################################################################
# score_level_fit
###############################################################################


class TestScoreLevelFit:
    def test_exact_match_returns_5(self):
        assert score_level_fit("senior", "senior") == 5.0

    def test_one_level_up_returns_4(self):
        # JD is one level above candidate: delta = 1
        assert score_level_fit("staff", "senior") == 4.0

    def test_one_level_down_returns_3(self):
        # JD is one level below candidate: delta = -1
        assert score_level_fit("senior", "staff") == 3.0

    def test_two_levels_up_returns_2(self):
        # JD is two levels above: delta = 2
        assert score_level_fit("principal", "senior") == 2.0

    def test_two_levels_down_returns_2(self):
        # JD is two levels below: delta = -2
        assert score_level_fit("senior", "principal") == 2.0

    def test_junior_to_vp_returns_2(self):
        # delta = 6, well above 1
        assert score_level_fit("vp", "junior") == 2.0

    def test_vp_to_junior_returns_2(self):
        # delta = -6
        assert score_level_fit("junior", "vp") == 2.0

    @pytest.mark.parametrize("level", ["junior", "mid", "senior", "staff", "principal", "director", "vp"])
    def test_all_seven_levels_exact_match(self, level):
        assert score_level_fit(level, level) == 5.0


###############################################################################
# score_archetype_fit
###############################################################################


class TestScoreArchetypeFit:
    def test_exact_match_returns_5(self):
        assert score_archetype_fit("ml-engineer", ["ml-engineer", "data-scientist"], 0.9) == 5.0

    def test_exact_match_with_low_adjacency_still_5(self):
        # Exact match always wins regardless of adjacency
        assert score_archetype_fit("ml-engineer", ["ml-engineer"], 0.1) == 5.0

    def test_adjacent_high_capped_at_4_5(self):
        # adjacency=0.8: 3.0 + 0.8*2.0 = 4.6, capped at 4.5
        assert score_archetype_fit("data-scientist", ["ml-engineer"], 0.8) == 4.5

    def test_adjacent_at_threshold_0_6(self):
        # adjacency=0.6: 3.0 + 0.6*2.0 = 4.2
        assert score_archetype_fit("data-scientist", ["ml-engineer"], 0.6) == pytest.approx(4.2)

    def test_middle_zone_0_45(self):
        # adjacency=0.45: in [0.3, 0.6) range: 2.5 + 0.45*2.5 = 3.625
        assert score_archetype_fit("data-scientist", ["ml-engineer"], 0.45) == pytest.approx(3.625)

    def test_wrong_function_low_0_1(self):
        # adjacency=0.1 < 0.3: 1.0 + 0.1*5.0 = 1.5
        assert score_archetype_fit("frontend-dev", ["ml-engineer"], 0.1) == pytest.approx(1.5)

    def test_wrong_function_zero_adjacency(self):
        # adjacency=0.0: 1.0 + 0.0*5.0 = 1.0
        assert score_archetype_fit("frontend-dev", ["ml-engineer"], 0.0) == pytest.approx(1.0)

    def test_boundary_just_below_0_6(self):
        # adjacency=0.599: in [0.3, 0.6): 2.5 + 0.599*2.5 = 3.9975
        assert score_archetype_fit("data-scientist", ["ml-engineer"], 0.599) == pytest.approx(3.9975)

    def test_boundary_just_below_0_3(self):
        # adjacency=0.299 < 0.3: 1.0 + 0.299*5.0 = 2.495
        assert score_archetype_fit("frontend-dev", ["ml-engineer"], 0.299) == pytest.approx(2.495)

    def test_boundary_exactly_0_3(self):
        # adjacency=0.3: in [0.3, 0.6) range: 2.5 + 0.3*2.5 = 3.25
        assert score_archetype_fit("data-scientist", ["ml-engineer"], 0.3) == pytest.approx(3.25)


###############################################################################
# score_cv_match
###############################################################################


class TestScoreCvMatch:
    def _req(self, priority: str, match_strength: float) -> Requirement:
        return Requirement(
            text="dummy",
            priority=priority,
            match_strength=match_strength,
            evidence="dummy",
        )

    def test_perfect_match_all_must_returns_5(self):
        reqs = [self._req("must", 1.0), self._req("must", 1.0)]
        assert score_cv_match(reqs) == pytest.approx(5.0)

    def test_zero_match_all_must_returns_1(self):
        reqs = [self._req("must", 0.0), self._req("must", 0.0)]
        assert score_cv_match(reqs) == pytest.approx(1.0)

    def test_mixed_priorities(self):
        # must=1.0 (w=3), preferred=0.0 (w=2), nice=0.5 (w=1)
        # weighted_sum = 1.0*3 + 0.0*2 + 0.5*1 = 3.5
        # total_weight = 6; raw = 3.5/6 = 0.5833...
        # score = 1.0 + 0.5833*4 = 3.3333...
        reqs = [self._req("must", 1.0), self._req("preferred", 0.0), self._req("nice", 0.5)]
        assert score_cv_match(reqs) == pytest.approx(1.0 + (3.5 / 6.0) * 4.0)

    def test_empty_requirements_returns_3(self):
        assert score_cv_match([]) == 3.0

    def test_all_preferred_mixed(self):
        # preferred=0.8 (w=2), preferred=0.6 (w=2)
        # weighted_sum = 0.8*2 + 0.6*2 = 2.8; total_weight = 4; raw = 0.7
        # score = 1.0 + 0.7*4 = 3.8
        reqs = [self._req("preferred", 0.8), self._req("preferred", 0.6)]
        assert score_cv_match(reqs) == pytest.approx(3.8)

    def test_single_must_partial_match(self):
        # must=0.5 (w=3); raw = 0.5; score = 1.0 + 0.5*4 = 3.0
        reqs = [self._req("must", 0.5)]
        assert score_cv_match(reqs) == pytest.approx(3.0)

    def test_must_dominates_nice(self):
        # must=0.0 (w=3), nice=1.0 x3 (w=1 each)
        # weighted_sum = 0.0*3 + 1.0*1 + 1.0*1 + 1.0*1 = 3.0
        # total_weight = 3+1+1+1 = 6; raw = 0.5
        # score = 1.0 + 0.5*4 = 3.0
        reqs = [self._req("must", 0.0), self._req("nice", 1.0), self._req("nice", 1.0), self._req("nice", 1.0)]
        assert score_cv_match(reqs) == pytest.approx(3.0)


###############################################################################
# score_org_risk
###############################################################################


class TestScoreOrgRisk:
    def _signals(
        self,
        glassdoor_rating: float | None = None,
        recent_layoffs: bool | None = None,
        org_stability: float = 4.0,
        remote_policy: str = "remote",
        location_fit: float = 5.0,
    ) -> OrgSignals:
        return OrgSignals(
            glassdoor_rating=glassdoor_rating,
            recent_layoffs=recent_layoffs,
            org_stability=org_stability,
            remote_policy=remote_policy,
            location_fit=location_fit,
        )

    def test_all_clean_high_scores(self):
        # glassdoor=4.5, layoffs=False(5.0), stability=4.9, remote=5.0, location=5.0
        # avg = (4.5+5.0+4.9+5.0+5.0)/5 = 24.4/5 = 4.88
        signals = self._signals(glassdoor_rating=4.5, recent_layoffs=False, org_stability=4.9)
        assert score_org_risk(signals) == pytest.approx(4.88)

    def test_all_bad_low_scores(self):
        # glassdoor=1.0, layoffs=True(2.0), stability=1.0, onsite=2.5, location=1.0
        # avg = (1.0+2.0+1.0+2.5+1.0)/5 = 7.5/5 = 1.5
        signals = self._signals(
            glassdoor_rating=1.0, recent_layoffs=True, org_stability=1.0,
            remote_policy="onsite", location_fit=1.0,
        )
        assert score_org_risk(signals) == pytest.approx(1.5)

    def test_missing_glassdoor_and_layoffs(self):
        # stability=3.0, remote=hybrid(4.0), location=4.0
        # avg = (3.0+4.0+4.0)/3 = 11.0/3 = 3.6667
        signals = self._signals(org_stability=3.0, remote_policy="hybrid", location_fit=4.0)
        assert score_org_risk(signals) == pytest.approx(11.0 / 3.0)

    def test_remote_policy_remote(self):
        signals = self._signals(org_stability=3.0, remote_policy="remote", location_fit=3.0)
        result = score_org_risk(signals)
        # scores = [3.0, 5.0, 3.0]; avg = 11.0/3
        assert result == pytest.approx(11.0 / 3.0)

    def test_remote_policy_hybrid(self):
        signals = self._signals(org_stability=3.0, remote_policy="hybrid", location_fit=3.0)
        result = score_org_risk(signals)
        # scores = [3.0, 4.0, 3.0]; avg = 10.0/3
        assert result == pytest.approx(10.0 / 3.0)

    def test_remote_policy_onsite(self):
        signals = self._signals(org_stability=3.0, remote_policy="onsite", location_fit=3.0)
        result = score_org_risk(signals)
        # scores = [3.0, 2.5, 3.0]; avg = 8.5/3
        assert result == pytest.approx(8.5 / 3.0)

    def test_remote_policy_unknown(self):
        signals = self._signals(org_stability=3.0, remote_policy="unknown", location_fit=3.0)
        result = score_org_risk(signals)
        # scores = [3.0, 3.0, 3.0]; avg = 3.0
        assert result == pytest.approx(3.0)

    def test_layoffs_true_penalizes(self):
        # glassdoor=4.5, layoffs=True(2.0), stability=4.5, remote=5.0, location=5.0
        # avg = (4.5+2.0+4.5+5.0+5.0)/5 = 21.0/5 = 4.2
        signals = self._signals(glassdoor_rating=4.5, recent_layoffs=True, org_stability=4.5)
        assert score_org_risk(signals) == pytest.approx(4.2)

    def test_layoffs_false_rewards(self):
        # glassdoor=4.5, layoffs=False(5.0), stability=4.5, remote=5.0, location=5.0
        # avg = (4.5+5.0+4.5+5.0+5.0)/5 = 24.0/5 = 4.8
        signals = self._signals(glassdoor_rating=4.5, recent_layoffs=False, org_stability=4.5)
        assert score_org_risk(signals) == pytest.approx(4.8)


###############################################################################
# score_blockers
###############################################################################


class TestScoreBlockers:
    def _blocker(self, severity: float) -> Blocker:
        return Blocker(type="domain", description="test blocker", severity=severity)

    def test_no_blockers_returns_5(self):
        assert score_blockers([]) == 5.0

    def test_single_absolute_blocker(self):
        assert score_blockers([self._blocker(1.0)]) == pytest.approx(1.0)

    def test_single_difficult_blocker(self):
        assert score_blockers([self._blocker(2.0)]) == pytest.approx(2.0)

    def test_multiple_uses_min(self):
        assert score_blockers([self._blocker(1.0), self._blocker(1.5)]) == pytest.approx(1.0)

    def test_mid_severity(self):
        assert score_blockers([self._blocker(1.5)]) == pytest.approx(1.5)


###############################################################################
# compute_global
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


class TestComputeGlobal:
    def test_strong_match_no_blockers(self):
        result = compute_global(_make_features())
        assert result.global_score >= 4.5
        assert result.blocker_gate_active is False

    def test_blocker_gate_caps_at_25(self):
        blocker = Blocker(
            type="citizenship",
            description="US only -- non-citizen",
            severity=1.0,
        )
        result = compute_global(_make_features(blockers=[blocker]))
        assert result.global_score <= 2.5
        assert result.blocker_gate_active is True
        assert "US only" in result.blocker_gate_reason

    def test_truncation_never_rounds_up(self):
        # Use requirements that produce a fractional weighted sum
        reqs = [
            Requirement(text="A", priority="must", match_strength=0.75, evidence="yes"),
            Requirement(text="B", priority="preferred", match_strength=0.65, evidence="yes"),
        ]
        result = compute_global(_make_features(requirements=reqs))
        # Verify truncation: floor(score * 10) / 10 == score (not rounded up)
        truncated = pytest.approx(result.global_score, abs=0.05)
        assert result.global_score * 10 == pytest.approx(
            int(result.global_score * 10), abs=0.001
        )

    def test_score_table_contains_all_dimensions(self):
        result = compute_global(_make_features())
        for name in ("CV Match", "Archetype Fit", "Comp Alignment", "Level Fit", "Org Risk", "Blockers"):
            assert name in result.score_table

    def test_interpretation_strong_match(self):
        result = compute_global(_make_features())
        assert "Strong match" in result.interpretation or "Good match" in result.interpretation

    def test_interpretation_below_threshold(self):
        bad_features = _make_features(
            salary_low=100000,
            salary_high=130000,
            comp_target=250000,
            jd_seniority="junior",
            candidate_seniority="staff",
            detected_archetype="frontend-dev",
            target_archetypes=["AI Platform/LLMOps"],
            archetype_adjacency=0.0,
            org_signals=OrgSignals(
                glassdoor_rating=1.5,
                recent_layoffs=True,
                org_stability=1.0,
                remote_policy="onsite",
                location_fit=1.0,
            ),
        )
        result = compute_global(bad_features)
        assert result.global_score < 3.5
        assert "Below threshold" in result.interpretation

    def test_dimensions_list_has_six_entries(self):
        result = compute_global(_make_features())
        assert len(result.dimensions) == 6

    def test_weighted_values_sum_to_global(self):
        result = compute_global(_make_features())
        weighted_sum = sum(d.weighted for d in result.dimensions)
        # global_score is truncated, so it can be up to 0.1 less than the sum
        assert weighted_sum - result.global_score < 0.11
        assert weighted_sum - result.global_score >= -0.001
