from __future__ import annotations

import logging

from scoring.models import JDFeatures, Warning

logger = logging.getLogger("scoring.normalize")

# Calibration-derived correction factor.
# Source: calibration-results.tsv (2026-04-13, N=11 dimension-scored reports).
# Claude over-rates match_strength by ~10-15% when requirements are numerous
# and uniformly high.  This is a design decision with limited statistical backing
# (N=11); revisit when N >= 30.
_MATCH_STRENGTH_DAMPENING = 0.90
_DAMPENING_MEAN_THRESHOLD = 0.85
_DAMPENING_MIN_REQUIREMENTS = 4


def normalize_features(
    features: JDFeatures,
) -> tuple[JDFeatures, list[Warning]]:
    """Apply calibration corrections to Claude's raw feature extraction.

    Returns a new JDFeatures (never mutates input) and any warnings generated
    during normalization.

    Layer 2 in the five-layer pipeline (see career-ops-scoring-architecture).
    """
    warnings: list[Warning] = []
    adjustments: dict = {}

    # --- Match strength dampening ---
    # When Claude extracts many requirements and rates them all highly,
    # the aggregate is systematically optimistic.  Scale down.
    if len(features.requirements) >= _DAMPENING_MIN_REQUIREMENTS:
        strengths = [r.match_strength for r in features.requirements]
        mean_strength = sum(strengths) / len(strengths)

        if mean_strength > _DAMPENING_MEAN_THRESHOLD:
            logger.info(
                "[NORMALIZE] Dampening match_strength: mean=%.2f across %d reqs (factor=%.2f)",
                mean_strength,
                len(strengths),
                _MATCH_STRENGTH_DAMPENING,
            )
            adjusted_reqs = [
                r.model_copy(update={
                    "match_strength": round(
                        r.match_strength * _MATCH_STRENGTH_DAMPENING, 2
                    ),
                })
                for r in features.requirements
            ]
            adjustments["requirements"] = adjusted_reqs
            warnings.append(Warning(
                tier="pre_computation",
                code="MATCH_STRENGTH_DAMPENED",
                message=(
                    f"Mean match_strength={mean_strength:.2f} across "
                    f"{len(strengths)} requirements; dampened by "
                    f"{_MATCH_STRENGTH_DAMPENING}"
                ),
            ))

    if adjustments:
        return features.model_copy(update=adjustments), warnings
    return features, warnings
