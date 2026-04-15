from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    text: str
    priority: Literal["must", "preferred", "nice"]
    match_strength: float = Field(ge=0.0, le=1.0)
    evidence: str


class OrgSignals(BaseModel):
    glassdoor_rating: float | None = Field(default=None, ge=1.0, le=5.0)
    recent_layoffs: bool | None = None
    org_stability: float = Field(ge=1.0, le=5.0)
    remote_policy: Literal["remote", "hybrid", "onsite", "unknown"]
    location_fit: float = Field(ge=1.0, le=5.0)


class Blocker(BaseModel):
    type: Literal["credentials", "citizenship", "experience_years", "domain", "geographic"]
    description: str
    severity: float = Field(ge=1.0, le=2.0)


class JDFeatures(BaseModel):
    salary_low: float | None = None
    salary_high: float | None = None
    salary_midpoint: float | None = None
    comp_target: float = Field(gt=0)

    jd_seniority: Literal["junior", "mid", "senior", "staff", "principal", "director", "vp"]
    candidate_seniority: Literal["junior", "mid", "senior", "staff", "principal", "director", "vp"]

    detected_archetype: str
    target_archetypes: list[str]
    archetype_adjacency: float = Field(ge=0.0, le=1.0)

    requirements: list[Requirement]
    org_signals: OrgSignals
    blockers: list[Blocker]


class DimensionScore(BaseModel):
    name: str
    score: float = Field(ge=1.0, le=5.0)
    weight: float
    weighted: float
    reasoning: str


class ScoreResult(BaseModel):
    dimensions: list[DimensionScore]
    global_score: float = Field(ge=1.0, le=5.0)
    blocker_gate_active: bool
    blocker_gate_reason: str | None = None
    interpretation: str
    score_table: str
