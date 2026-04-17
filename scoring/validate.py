from __future__ import annotations

import logging

from scoring.models import JDFeatures, Warning

logger = logging.getLogger("scoring.validate")


###############################################################################
# Pre-computation: check feature coherence before scoring
###############################################################################


def validate_features(features: JDFeatures) -> list[Warning]:
    """Validate extracted features for internal coherence.

    Runs before scoring.  Every check produces a Warning, not a hard failure.
    The analyst decides what to do with the warnings.
    """
    warnings: list[Warning] = []

    # Salary bounds inverted
    if (
        features.salary_low is not None
        and features.salary_high is not None
        and features.salary_low > features.salary_high
    ):
        warnings.append(Warning(
            tier="pre_computation",
            code="SALARY_INVERTED",
            message=(
                f"salary_low ({features.salary_low:,.0f}) > "
                f"salary_high ({features.salary_high:,.0f})"
            ),
        ))

    # All match_strength values identical across 3+ requirements
    if len(features.requirements) > 2:
        strengths = {r.match_strength for r in features.requirements}
        if len(strengths) == 1:
            warnings.append(Warning(
                tier="pre_computation",
                code="UNIFORM_MATCH_STRENGTH",
                message=(
                    f"All {len(features.requirements)} requirements have "
                    f"identical match_strength={next(iter(strengths))}"
                ),
            ))

    # Adjacency set but archetype is already an exact match
    if (
        features.detected_archetype in features.target_archetypes
        and features.archetype_adjacency < 1.0
    ):
        warnings.append(Warning(
            tier="pre_computation",
            code="ADJACENCY_WITH_EXACT_MATCH",
            message=(
                f"archetype_adjacency={features.archetype_adjacency} but "
                f"detected archetype '{features.detected_archetype}' is in target list"
            ),
        ))

    # Salary is a point estimate (both bounds identical, no midpoint)
    if (
        features.salary_low is not None
        and features.salary_high is not None
        and features.salary_low == features.salary_high
        and features.salary_midpoint is None
    ):
        warnings.append(Warning(
            tier="pre_computation",
            code="SALARY_POINT_ESTIMATE",
            message=(
                f"salary_low == salary_high == {features.salary_low:,.0f} "
                f"-- likely a point estimate, not a posted range"
            ),
        ))

    if warnings:
        for w in warnings:
            logger.info("[VALIDATE PRE] %s: %s", w.code, w.message)

    return warnings


###############################################################################
# Post-computation: check that scores make sense given features
###############################################################################


def validate_scores(
    dim_scores: dict[str, float],
    features: JDFeatures,
) -> list[Warning]:
    """Validate dimension scores for internal consistency.

    Runs after scoring but before global aggregation.
    """
    warnings: list[Warning] = []
    scores = list(dim_scores.values())

    # All dimensions within 0.5 -- no discrimination
    if len(scores) >= 2 and (max(scores) - min(scores)) < 0.5:
        warnings.append(Warning(
            tier="post_computation",
            code="UNIFORM_SCORES",
            message=(
                f"All dimension scores within 0.5 range "
                f"({min(scores):.1f}-{max(scores):.1f}), no discrimination"
            ),
        ))

    # Strong CV match contradicted by hard blockers
    cv_match = dim_scores.get("CV Match", 0.0)
    blockers = dim_scores.get("Blockers", 5.0)
    if cv_match >= 4.5 and blockers <= 2.0:
        warnings.append(Warning(
            tier="post_computation",
            code="MATCH_BLOCKER_CONTRADICTION",
            message=(
                f"CV Match={cv_match:.1f} but Blockers={blockers:.1f} "
                f"-- strong match with hard blockers is contradictory"
            ),
        ))

    # High comp but low level fit (overpaying for a step-down role?)
    comp = dim_scores.get("Comp Alignment", 3.0)
    level = dim_scores.get("Level Fit", 3.0)
    if comp >= 5.0 and level <= 2.5:
        warnings.append(Warning(
            tier="post_computation",
            code="COMP_LEVEL_MISMATCH",
            message=(
                f"Comp Alignment={comp:.1f} but Level Fit={level:.1f} "
                f"-- high pay for a mismatched level may signal different role scope"
            ),
        ))

    if warnings:
        for w in warnings:
            logger.info("[VALIDATE POST] %s: %s", w.code, w.message)

    return warnings
