from __future__ import annotations

import pytest

from scoring.engine import score_archetype_fit, score_comp_alignment, score_level_fit


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
