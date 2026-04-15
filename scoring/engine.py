from __future__ import annotations

import math

from scoring.models import Blocker, DimensionScore, JDFeatures, OrgSignals, Requirement, ScoreResult


def _effective_salary(
    low: float | None,
    high: float | None,
    midpoint: float | None,
) -> float | None:
    if midpoint is not None:
        return midpoint
    if low is not None and high is not None:
        return (low + high) / 2
    if low is not None:
        return low
    if high is not None:
        return high
    return None


def score_comp_alignment(
    salary_low: float | None,
    salary_high: float | None,
    comp_target: float,
    *,
    salary_midpoint: float | None = None,
) -> float:
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


_LEVEL_ORDER = {
    "junior": 0, "mid": 1, "senior": 2, "staff": 3,
    "principal": 4, "director": 5, "vp": 6,
}


def score_level_fit(jd_seniority: str, candidate_seniority: str) -> float:
    delta = _LEVEL_ORDER[jd_seniority] - _LEVEL_ORDER[candidate_seniority]
    if delta == 0:
        return 5.0
    if delta == 1:
        return 4.0
    if delta == -1:
        return 3.0
    return 2.0


def score_archetype_fit(
    detected_archetype: str,
    target_archetypes: list[str],
    archetype_adjacency: float,
) -> float:
    if detected_archetype in target_archetypes:
        return 5.0
    if archetype_adjacency >= 0.6:
        return min(3.0 + archetype_adjacency * 2.0, 4.5)
    if archetype_adjacency < 0.3:
        return 1.0 + archetype_adjacency * 5.0
    return 2.5 + archetype_adjacency * 2.5


_PRIORITY_WEIGHTS = {"must": 3, "preferred": 2, "nice": 1}


def score_cv_match(requirements: list[Requirement]) -> float:
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


_REMOTE_POLICY_SCORES = {
    "remote": 5.0,
    "hybrid": 4.0,
    "onsite": 2.5,
    "unknown": 3.0,
}


def score_org_risk(org_signals: OrgSignals) -> float:
    scores: list[float] = []

    if org_signals.glassdoor_rating is not None:
        scores.append(org_signals.glassdoor_rating)

    if org_signals.recent_layoffs is not None:
        scores.append(2.0 if org_signals.recent_layoffs else 5.0)

    scores.append(org_signals.org_stability)
    scores.append(_REMOTE_POLICY_SCORES[org_signals.remote_policy])
    scores.append(org_signals.location_fit)

    return sum(scores) / len(scores)


def score_blockers(blockers: list[Blocker]) -> float:
    if not blockers:
        return 5.0
    return min(b.severity for b in blockers)


###############################################################################
# Global scoring
###############################################################################

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
    return math.floor(value * 10) / 10


def _format_score_table(dimensions: list[DimensionScore], global_score: float) -> str:
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
            reasoning="",
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
