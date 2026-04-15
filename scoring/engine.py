from __future__ import annotations


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
