"""The extraction schema is strict — malformed model output is rejected."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from playbook_shared.extraction_schemas import ExtractedSlot, TurnExtraction


def test_valid_extraction_parses():
    parsed = TurnExtraction.model_validate(
        {"extractions": [{"slot_key": "ctx.role", "value": "Controller", "confidence": 0.9}]}
    )
    assert parsed.extractions[0].slot_key == "ctx.role"
    assert parsed.extractions[0].confidence == 0.9


def test_missing_required_field_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedSlot.model_validate({"slot_key": "ctx.role", "value": "Controller"})  # no confidence


def test_wrong_type_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedSlot.model_validate(
            {"slot_key": "ctx.role", "value": "Controller", "confidence": "high"}
        )


def test_extractions_must_be_a_list():
    with pytest.raises(ValidationError):
        TurnExtraction.model_validate({"extractions": "ctx.role"})
