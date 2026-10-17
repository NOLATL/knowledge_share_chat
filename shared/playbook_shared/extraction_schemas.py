"""Pydantic schemas for the structured-extraction call (GR2 call B, GR4 strict).

Used with OpenAI Structured Outputs (`strict: true`). Kept in `shared` so the
synthetic-data generator (Epic 2) can reuse the exact same shape, making
synthetic and real `answers` interchangeable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedSlot(BaseModel):
    """One slot value the user's turn addressed."""

    slot_key: str = Field(description="The slot_key this value answers (from the provided list).")
    value: str = Field(description="The extracted/normalized value, as concise text.")
    confidence: float = Field(description="Extraction confidence in [0, 1].")


class TurnExtraction(BaseModel):
    """All slots addressed by a single user turn (empty if none)."""

    extractions: list[ExtractedSlot]
