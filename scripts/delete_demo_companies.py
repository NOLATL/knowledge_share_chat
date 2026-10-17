"""CLI: delete placeholder demo companies and all their dependent records.

Run locally or as a Railway one-off (needs DATABASE_URL; no OpenAI calls):

    uv run python scripts/delete_demo_companies.py

Removes "Demo discovery company" / "Document demo company" shells with their
sessions, answers, respondents, and benchmark history. Real (named) companies
are untouched. Run POST /admin/recompute afterwards so cohort counts settle.
"""

from __future__ import annotations

import sys

from playbook_shared.demo_cleanup import delete_demo_companies


def main() -> int:
    result = delete_demo_companies()
    print("Demo company cleanup complete:")
    print(f"  companies:   {result.companies}")
    print(f"  respondents: {result.respondents}")
    print(f"  sessions:    {result.sessions}")
    print(f"  answers:     {result.answers}")
    if result.companies:
        print("Run POST /admin/recompute so cohort counts settle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
