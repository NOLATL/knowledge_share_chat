"""CLI to sync the question bank YAML into the database.

Run locally or as a Railway one-off:

    uv run python scripts/reseed_questions.py

Reads DATABASE_URL from the environment. Upserts by slot_key; retires (never
deletes) slot_keys absent from the file; refuses to run on duplicate slot_keys
and warns loudly when a slot_key with existing answers would be retired.
"""

from __future__ import annotations

import sys

from playbook_shared.question_bank import QuestionBankError, reseed_questions


def main() -> int:
    try:
        result = reseed_questions()
    except QuestionBankError as err:
        print(f"ERROR: refusing to reseed — {err}", file=sys.stderr)
        return 1

    print(f"Reseeded question bank version {result.version}:")
    print(f"  inserted: {len(result.inserted)}")
    print(f"  updated:  {len(result.updated)}")
    print(f"  retired:  {len(result.retired)}")
    for slot_key in result.retired_with_answers:
        print(
            f"  !! WARNING: retired slot_key '{slot_key}' has existing answers — "
            "historical data is preserved, but it is no longer asked.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
