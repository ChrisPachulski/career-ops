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


###############################################################################
# Diagnostics and validation types
###############################################################################


class Warning(BaseModel):
    tier: Literal["pre_computation", "post_computation", "cross_evaluation"]
    code: str
    message: str


class DiagnosticStep(BaseModel):
    dimension: str
    inputs: dict[str, str]
    computation: str
    threshold_hit: str
    sensitivity: list[str] = []


class DiagnosticTrace(BaseModel):
    steps: list[DiagnosticStep]


###############################################################################
# Configuration
###############################################################################


class CompThresholds(BaseModel):
    band_4_min: float = 0.86
    band_3_min: float = 0.71
    unknown_default: float = 3.0


class BlockerGate(BaseModel):
    hard_cap: float = 2.0
    hard_max_severity: float = 1.3
    medium_cap: float = 3.0
    medium_max_severity: float = 1.6
    soft_penalty: float = 0.5


class ScoreConfig(BaseModel):
    comp_thresholds: CompThresholds = CompThresholds()
    blocker_gate: BlockerGate = BlockerGate()
    weights: dict[str, float] = Field(default_factory=lambda: {
        "CV Match": 0.25,
        "Archetype Fit": 0.20,
        "Comp Alignment": 0.20,
        "Level Fit": 0.15,
        "Org Risk": 0.10,
        "Blockers": 0.10,
    })


###############################################################################
# Score result
###############################################################################


class ScoreResult(BaseModel):
    dimensions: list[DimensionScore]
    global_score: float = Field(ge=1.0, le=5.0)
    blocker_gate_active: bool
    blocker_gate_reason: str | None = None
    interpretation: str
    score_table: str
    warnings: list[Warning] = []
    diagnostic_trace: DiagnosticTrace | None = None
