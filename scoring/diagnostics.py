from __future__ import annotations

from scoring.models import (
    DiagnosticStep,
    DiagnosticTrace,
    JDFeatures,
    ScoreConfig,
)


def _fmt(v: float | None) -> str:
    if v is None:
        return "None"
    return f"${v / 1000:.0f}K"


###############################################################################
# Per-dimension trace builders
###############################################################################


def _trace_comp(features: JDFeatures, score: float, config: ScoreConfig) -> DiagnosticStep:
    effective = features.salary_midpoint
    if effective is None and features.salary_low is not None and features.salary_high is not None:
        effective = (features.salary_low + features.salary_high) / 2
    elif effective is None:
        effective = features.salary_low or features.salary_high

    inputs = {
        "salary_low": _fmt(features.salary_low),
        "salary_high": _fmt(features.salary_high),
        "midpoint": _fmt(features.salary_midpoint),
        "comp_target": _fmt(features.comp_target),
    }

    if effective is None:
        return DiagnosticStep(
            dimension="Comp Alignment",
            inputs=inputs,
            computation="No salary data -- using default",
            threshold_hit=f"default → {config.comp_thresholds.unknown_default:.1f}",
        )

    ratio = effective / features.comp_target
    inputs["effective"] = _fmt(effective)
    thresholds = config.comp_thresholds

    if ratio >= 1.0:
        band = f"{ratio:.3f} >= 1.000 → score 5.0"
    elif ratio >= thresholds.band_4_min:
        band = f"{ratio:.3f} >= {thresholds.band_4_min} → score 4.0"
    elif ratio >= thresholds.band_3_min:
        band = f"{ratio:.3f} >= {thresholds.band_3_min} → score 3.0"
    else:
        band = f"{ratio:.3f} < {thresholds.band_3_min} → score 2.0"

    sensitivity: list[str] = []
    if ratio < 1.0:
        needed = features.comp_target - effective
        sensitivity.append(f"+{_fmt(needed)} to effective → ratio 1.0 → score 5.0")
    if ratio < thresholds.band_4_min:
        needed = features.comp_target * thresholds.band_4_min - effective
        sensitivity.append(f"+{_fmt(needed)} to effective → ratio {thresholds.band_4_min} → score 4.0")

    return DiagnosticStep(
        dimension="Comp Alignment",
        inputs=inputs,
        computation=f"{_fmt(effective)} / {_fmt(features.comp_target)} = {ratio:.3f}",
        threshold_hit=band,
        sensitivity=sensitivity,
    )


def _trace_level(features: JDFeatures, score: float) -> DiagnosticStep:
    _order = {"junior": 0, "mid": 1, "senior": 2, "staff": 3, "principal": 4, "director": 5, "vp": 6}
    delta = _order[features.jd_seniority] - _order[features.candidate_seniority]
    direction = "stretch up" if delta > 0 else "step down" if delta < 0 else "exact match"

    return DiagnosticStep(
        dimension="Level Fit",
        inputs={
            "jd_seniority": features.jd_seniority,
            "candidate_seniority": features.candidate_seniority,
        },
        computation=f"delta = {delta:+d} ({direction})",
        threshold_hit=f"delta {delta:+d} → score {score:.1f}",
    )


def _trace_archetype(features: JDFeatures, score: float) -> DiagnosticStep:
    exact = features.detected_archetype in features.target_archetypes
    return DiagnosticStep(
        dimension="Archetype Fit",
        inputs={
            "detected": features.detected_archetype,
            "targets": ", ".join(features.target_archetypes),
            "adjacency": f"{features.archetype_adjacency:.2f}",
        },
        computation="exact match" if exact else f"adjacency={features.archetype_adjacency:.2f}",
        threshold_hit=f"→ score {score:.1f}",
    )


def _trace_cv_match(features: JDFeatures, score: float) -> DiagnosticStep:
    by_priority: dict[str, list[float]] = {"must": [], "preferred": [], "nice": []}
    for r in features.requirements:
        by_priority[r.priority].append(r.match_strength)

    inputs: dict[str, str] = {}
    for p, vals in by_priority.items():
        if vals:
            mean = sum(vals) / len(vals)
            inputs[f"{p} ({len(vals)})"] = f"mean={mean:.2f}"

    return DiagnosticStep(
        dimension="CV Match",
        inputs=inputs,
        computation=f"{len(features.requirements)} requirements, weighted by priority",
        threshold_hit=f"→ score {score:.1f}",
    )


def _trace_org_risk(features: JDFeatures, score: float) -> DiagnosticStep:
    signals = features.org_signals
    inputs: dict[str, str] = {
        "org_stability": f"{signals.org_stability:.1f}",
        "remote_policy": signals.remote_policy,
        "location_fit": f"{signals.location_fit:.1f}",
    }
    if signals.glassdoor_rating is not None:
        inputs["glassdoor"] = f"{signals.glassdoor_rating:.1f}"
    if signals.recent_layoffs is not None:
        inputs["recent_layoffs"] = str(signals.recent_layoffs)

    return DiagnosticStep(
        dimension="Org Risk",
        inputs=inputs,
        computation=f"mean of {len(inputs)} signals",
        threshold_hit=f"→ score {score:.1f}",
    )


def _trace_blockers(features: JDFeatures, score: float) -> DiagnosticStep:
    if not features.blockers:
        return DiagnosticStep(
            dimension="Blockers",
            inputs={"count": "0"},
            computation="no blockers",
            threshold_hit="→ score 5.0",
        )

    inputs = {
        f"{b.type}": f"severity={b.severity:.1f} -- {b.description}"
        for b in features.blockers
    }
    min_sev = min(b.severity for b in features.blockers)

    return DiagnosticStep(
        dimension="Blockers",
        inputs=inputs,
        computation=f"{len(features.blockers)} blockers, min severity={min_sev:.1f}",
        threshold_hit=f"→ score {score:.1f}",
    )


###############################################################################
# Top-level trace builder
###############################################################################


def build_trace(
    features: JDFeatures,
    dim_scores: dict[str, float],
    config: ScoreConfig,
) -> DiagnosticTrace:
    """Build a full diagnostic trace for all dimensions."""
    steps = [
        _trace_comp(features, dim_scores.get("Comp Alignment", 3.0), config),
        _trace_level(features, dim_scores.get("Level Fit", 3.0)),
        _trace_archetype(features, dim_scores.get("Archetype Fit", 3.0)),
        _trace_cv_match(features, dim_scores.get("CV Match", 3.0)),
        _trace_org_risk(features, dim_scores.get("Org Risk", 3.0)),
        _trace_blockers(features, dim_scores.get("Blockers", 5.0)),
    ]
    return DiagnosticTrace(steps=steps)
