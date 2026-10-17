"""Small typed containers shared by the analytics pipeline."""

from __future__ import annotations

from dataclasses import dataclass


EMBEDDING_DIM = 1536


@dataclass(frozen=True)
class RespondentProfile:
    respondent_id: str
    source: str
    role: str | None
    answers: dict[str, str]
    # Company identity for the company-level rollup (Task 8.2).
    company_id: str | None = None
    company_industry: str | None = None
    company_size_band: str | None = None


@dataclass(frozen=True)
class FeatureProfile:
    respondent_id: str
    source: str
    feature_vector: dict[str, float | int | str | list[str]]
    profile_text: str
    maturity_score: float


@dataclass(frozen=True)
class EntityProfile:
    """A function- or company-grain unit for the multi-grain redesign (Fork B).

    `key` is the entity key (company_id for company grain, 'company_id:function_key'
    for function grain). `profile` reuses RespondentProfile so build_feature_profile
    works unchanged on the entity's aggregated (latest-per-slot) answers.
    """

    key: str
    grain: str  # 'function' | 'company'
    company_id: str | None
    function_key: str | None
    industry: str | None
    size_band: str | None
    member_count: int
    profile: RespondentProfile
