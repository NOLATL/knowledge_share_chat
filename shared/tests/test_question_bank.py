"""Validation + shape of the shipped question bank (no DB needed)."""

from __future__ import annotations

import pytest

from playbook_shared.question_bank import (
    FRAMEWORK_PREFIXES,
    VALID_CATEGORIES,
    VALID_TIERS,
    QuestionBankError,
    get_active_version,
    load_bank,
)


def test_loads_with_version():
    bank = load_bank()
    assert bank.version
    assert get_active_version() == bank.version


def test_at_least_12_must_fill_spanning_all_categories():
    bank = load_bank()
    must_fill = bank.must_fill
    assert len(must_fill) >= 12
    assert {q.category for q in must_fill} == VALID_CATEGORIES  # all six A–F


def test_every_row_has_valid_tier_category_framework():
    bank = load_bank()
    for q in bank.questions:
        assert q.tier in VALID_TIERS
        assert q.category in VALID_CATEGORIES
        assert q.framework_tag.startswith(FRAMEWORK_PREFIXES)
        assert q.text.strip()


def test_slot_keys_are_unique():
    bank = load_bank()
    keys = [q.slot_key for q in bank.questions]
    assert len(keys) == len(set(keys))


def test_duplicate_slot_key_is_rejected(tmp_path):
    bad = tmp_path / "bank.yaml"
    bad.write_text(
        """
version: "test.1"
questions:
  - {slot_key: dup.key, category: A, text: "one", framework_tag: SPIN-Situation, tier: must_fill, order_hint: 10, active: true}
  - {slot_key: dup.key, category: B, text: "two", framework_tag: SPIN-Problem, tier: nice_to_have, order_hint: 20, active: true}
""",
        encoding="utf-8",
    )
    with pytest.raises(QuestionBankError, match="duplicate slot_key"):
        load_bank(bad)


def test_invalid_framework_tag_is_rejected(tmp_path):
    bad = tmp_path / "bank.yaml"
    bad.write_text(
        """
version: "test.1"
questions:
  - {slot_key: a.b, category: A, text: "x", framework_tag: NOPE, tier: must_fill, order_hint: 10, active: true}
""",
        encoding="utf-8",
    )
    with pytest.raises(QuestionBankError, match="framework_tag"):
        load_bank(bad)
