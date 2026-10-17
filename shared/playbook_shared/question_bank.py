"""Load, validate, and reseed the question bank (the discovery "script").

`shared/question_bank.yaml` is the single source of truth. ``load_bank`` parses
and validates it; ``reseed_questions`` upserts it into the ``questions`` table by
``slot_key`` (insert new, update existing, retire missing — never delete, never
rename). The conversation engine reads the active set from the DB at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from playbook_shared.db import connect

BANK_PATH = Path(__file__).resolve().parents[1] / "question_bank.yaml"

VALID_CATEGORIES = {"A", "B", "C", "D", "E", "F"}
VALID_TIERS = {"must_fill", "nice_to_have"}
FRAMEWORK_PREFIXES = ("SPIN-", "MEDDIC-", "JTBD-")
_REQUIRED_FIELDS = ("slot_key", "category", "text", "framework_tag", "tier", "order_hint")


class QuestionBankError(Exception):
    """Raised when the question bank file is malformed or internally invalid."""


@dataclass(frozen=True)
class Question:
    slot_key: str
    category: str
    text: str
    framework_tag: str
    tier: str
    order_hint: int
    active: bool = True


@dataclass(frozen=True)
class QuestionBank:
    version: str
    questions: list[Question]

    @property
    def must_fill(self) -> list[Question]:
        return [q for q in self.questions if q.tier == "must_fill"]


def load_bank(path: Path | str | None = None) -> QuestionBank:
    path = Path(path) if path else BANK_PATH
    if not path.is_file():
        raise QuestionBankError(f"question bank not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    version = raw.get("version")
    if not version or not isinstance(version, str):
        raise QuestionBankError("question bank is missing a string `version`")

    rows = raw.get("questions")
    if not isinstance(rows, list) or not rows:
        raise QuestionBankError("question bank has no `questions`")

    questions: list[Question] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise QuestionBankError(f"question #{i} is not a mapping")
        for field in _REQUIRED_FIELDS:
            if field not in row or row[field] in (None, ""):
                raise QuestionBankError(f"question #{i} is missing `{field}`")

        slot_key = str(row["slot_key"])
        if slot_key in seen:
            raise QuestionBankError(f"duplicate slot_key: {slot_key!r}")
        seen.add(slot_key)

        category = str(row["category"])
        if category not in VALID_CATEGORIES:
            raise QuestionBankError(f"{slot_key}: invalid category {category!r}")

        tier = str(row["tier"])
        if tier not in VALID_TIERS:
            raise QuestionBankError(f"{slot_key}: invalid tier {tier!r}")

        framework_tag = str(row["framework_tag"])
        if not framework_tag.startswith(FRAMEWORK_PREFIXES):
            raise QuestionBankError(f"{slot_key}: invalid framework_tag {framework_tag!r}")

        try:
            order_hint = int(row["order_hint"])
        except (TypeError, ValueError) as err:
            raise QuestionBankError(f"{slot_key}: order_hint must be an int") from err

        questions.append(
            Question(
                slot_key=slot_key,
                category=category,
                text=str(row["text"]),
                framework_tag=framework_tag,
                tier=tier,
                order_hint=order_hint,
                active=bool(row.get("active", True)),
            )
        )

    return QuestionBank(version=version, questions=questions)


def get_active_version(path: Path | str | None = None) -> str:
    """The script version a new session should record in `sessions.script_version`."""
    return load_bank(path).version


@dataclass
class ReseedResult:
    version: str
    inserted: list[str]
    updated: list[str]
    retired: list[str]
    retired_with_answers: list[str]


def reseed_questions(
    database_url: str | None = None,
    bank_path: Path | str | None = None,
) -> ReseedResult:
    """Sync the YAML into the `questions` table. Idempotent; never deletes.

    Raises QuestionBankError (before touching the DB) if the file has duplicate
    slot_keys or is otherwise invalid.
    """
    bank = load_bank(bank_path)
    bank_keys = {q.slot_key for q in bank.questions}

    inserted: list[str] = []
    updated: list[str] = []
    retired: list[str] = []
    retired_with_answers: list[str] = []

    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slot_key FROM questions")
            existing = {row[0] for row in cur.fetchall()}

            for q in bank.questions:
                cur.execute(
                    """
                    INSERT INTO questions
                        (slot_key, category, text, framework_tag, tier, order_hint, active, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, true, now())
                    ON CONFLICT (slot_key) DO UPDATE SET
                        category      = EXCLUDED.category,
                        text          = EXCLUDED.text,
                        framework_tag = EXCLUDED.framework_tag,
                        tier          = EXCLUDED.tier,
                        order_hint    = EXCLUDED.order_hint,
                        active        = true,
                        updated_at    = now()
                    """,
                    (q.slot_key, q.category, q.text, q.framework_tag, q.tier, q.order_hint),
                )
                (updated if q.slot_key in existing else inserted).append(q.slot_key)

            # Retire DB slot_keys no longer in the file (never delete).
            to_retire = sorted(existing - bank_keys)
            for slot_key in to_retire:
                cur.execute(
                    "SELECT 1 FROM answers WHERE slot_key = %s LIMIT 1",
                    (slot_key,),
                )
                if cur.fetchone() is not None:
                    retired_with_answers.append(slot_key)
                cur.execute(
                    "UPDATE questions SET active = false, updated_at = now() "
                    "WHERE slot_key = %s AND active = true",
                    (slot_key,),
                )
                retired.append(slot_key)
    finally:
        conn.close()

    return ReseedResult(
        version=bank.version,
        inserted=inserted,
        updated=updated,
        retired=retired,
        retired_with_answers=retired_with_answers,
    )
