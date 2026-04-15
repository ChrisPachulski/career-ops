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


def score_level_fit(jd_seniority: str, candidate_seniority: str) -> float:
    raise NotImplementedError
