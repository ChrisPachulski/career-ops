from __future__ import annotations

import pytest

from scoring.compare import compare_results, format_comparison_table
from scoring.models import DimensionScore, ScoreResult


###############################################################################
# Fixtures / helpers
###############################################################################


def _dim(name: str, score: float, weight: float = 0.25) -> DimensionScore:
    return DimensionScore(
        name=name,
        score=score,
        weight=weight,
        weighted=round(score * weight, 2),
        reasoning=f"{name} reasoning",
    )


def _result(
    global_score: float,
    dim_scores: dict[str, float] | None = None,
) -> ScoreResult:
    """Build a minimal ScoreResult with two dimensions."""
    scores = dim_scores or {"CV Match": 4.0, "Comp Alignment": 3.5}
    dims = [_dim(name, score) for name, score in scores.items()]
    return ScoreResult(
        dimensions=dims,
        global_score=global_score,
        blocker_gate_active=False,
        blocker_gate_reason=None,
        interpretation="test interpretation",
        score_table="| dim | score |",
    )


DIM_NAMES = ["CV Match", "Comp Alignment"]


###############################################################################
# compare_results -- empty input
###############################################################################


def test_compare_results_empty_input_returns_empty_list():
    assert compare_results([]) == []


###############################################################################
# compare_results -- single result
###############################################################################


def test_single_result_rank_is_one():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    assert len(rows) == 1
    assert rows[0]["rank"] == 1


def test_single_result_preserves_label_and_global_score():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    assert rows[0]["label"] == "Acme -- SWE"
    assert rows[0]["global_score"] == 4.2


def test_single_result_deltas_are_all_zero():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    assert rows[0]["delta_CV Match"] == 0.0
    assert rows[0]["delta_Comp Alignment"] == 0.0


def test_single_result_indices_are_all_one():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    assert rows[0]["index_CV Match"] == 1.0
    assert rows[0]["index_Comp Alignment"] == 1.0


def test_single_result_has_dimension_scores():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    assert rows[0]["CV Match"] == 4.0
    assert rows[0]["Comp Alignment"] == 3.5


###############################################################################
# compare_results -- two results (ranking, deltas, indices)
###############################################################################


def _two_result_rows() -> list[dict[str, object]]:
    """Two offers: higher-scoring first after sort."""
    high = _result(4.5, {"CV Match": 5.0, "Comp Alignment": 4.0})
    low = _result(3.0, {"CV Match": 3.0, "Comp Alignment": 2.0})
    return compare_results([
        ("Beta -- Analyst", low),
        ("Alpha -- Lead", high),
    ])


def test_two_results_sorted_by_global_score_descending():
    rows = _two_result_rows()
    assert rows[0]["label"] == "Alpha -- Lead"
    assert rows[1]["label"] == "Beta -- Analyst"


def test_two_results_ranks_assigned_correctly():
    rows = _two_result_rows()
    assert rows[0]["rank"] == 1
    assert rows[1]["rank"] == 2


def test_two_results_best_offer_deltas_are_zero():
    rows = _two_result_rows()
    assert rows[0]["delta_CV Match"] == 0.0
    assert rows[0]["delta_Comp Alignment"] == 0.0


def test_two_results_second_offer_deltas_are_negative():
    rows = _two_result_rows()
    assert rows[1]["delta_CV Match"] == -2.0
    assert rows[1]["delta_Comp Alignment"] == -2.0


def test_two_results_index_above_mean_greater_than_one():
    rows = _two_result_rows()
    # CV Match mean = (5.0 + 3.0) / 2 = 4.0; best = 5.0 / 4.0 = 1.25
    assert rows[0]["index_CV Match"] == 1.25


def test_two_results_index_below_mean_less_than_one():
    rows = _two_result_rows()
    # CV Match mean = 4.0; second = 3.0 / 4.0 = 0.75
    assert rows[1]["index_CV Match"] == 0.75


def test_two_results_index_comp_alignment():
    rows = _two_result_rows()
    # Comp Alignment mean = (4.0 + 2.0) / 2 = 3.0
    # best: 4.0 / 3.0 = 1.333... -> rounded to 1.33
    assert rows[0]["index_Comp Alignment"] == 1.33
    # second: 2.0 / 3.0 = 0.666... -> rounded to 0.67
    assert rows[1]["index_Comp Alignment"] == 0.67


###############################################################################
# compare_results -- tied global scores preserve insertion order
###############################################################################


def test_tied_scores_both_get_sequential_ranks():
    a = _result(4.0)
    b = _result(4.0)
    rows = compare_results([("Tied A", a), ("Tied B", b)])
    assert rows[0]["rank"] == 1
    assert rows[1]["rank"] == 2


###############################################################################
# format_comparison_table -- empty input
###############################################################################


def test_format_table_empty_rows_returns_empty_string():
    assert format_comparison_table([], DIM_NAMES) == ""


###############################################################################
# format_comparison_table -- structure
###############################################################################


def test_format_table_has_header_separator_and_data_rows():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    table = format_comparison_table(rows, DIM_NAMES)
    lines = table.strip().split("\n")
    # header, separator, one data row
    assert len(lines) == 3


def test_format_table_header_contains_rank_offer_score():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    table = format_comparison_table(rows, DIM_NAMES)
    header = table.split("\n")[0]
    assert "Rank" in header
    assert "Offer" in header
    assert "Score" in header


def test_format_table_header_contains_dimension_names():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    table = format_comparison_table(rows, DIM_NAMES)
    header = table.split("\n")[0]
    for dim in DIM_NAMES:
        assert dim in header


def test_format_table_separator_is_second_line():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    table = format_comparison_table(rows, DIM_NAMES)
    sep = table.split("\n")[1]
    assert sep.startswith("|")
    assert "---" in sep


def test_format_table_data_row_contains_label_and_score():
    rows = compare_results([("Acme -- SWE", _result(4.2))])
    table = format_comparison_table(rows, DIM_NAMES)
    data_row = table.split("\n")[2]
    assert "Acme -- SWE" in data_row
    assert "4.2" in data_row


def test_format_table_shows_delta_for_non_best():
    high = _result(4.5, {"CV Match": 5.0, "Comp Alignment": 4.0})
    low = _result(3.0, {"CV Match": 3.0, "Comp Alignment": 2.0})
    rows = compare_results([("Best", high), ("Worse", low)])
    table = format_comparison_table(rows, DIM_NAMES)
    lines = table.split("\n")
    best_row = lines[2]
    worse_row = lines[3]
    # Best row should NOT have delta markers
    assert "(+" not in best_row
    assert "(-" not in best_row
    # Worse row should have negative deltas
    assert "(-2.0)" in worse_row


def test_format_table_multiple_rows_produces_correct_line_count():
    a = _result(4.5, {"CV Match": 5.0, "Comp Alignment": 4.0})
    b = _result(3.5, {"CV Match": 3.0, "Comp Alignment": 3.0})
    c = _result(2.5, {"CV Match": 2.0, "Comp Alignment": 2.0})
    rows = compare_results([("A", a), ("B", b), ("C", c)])
    table = format_comparison_table(rows, DIM_NAMES)
    lines = table.strip().split("\n")
    # header + separator + 3 data rows
    assert len(lines) == 5
