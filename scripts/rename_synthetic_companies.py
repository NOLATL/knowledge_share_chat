"""CLI: one-off rename of placeholder synthetic companies to plausible,
industry-appropriate fictional names (no OpenAI calls; needs DATABASE_URL):

    uv run python scripts/rename_synthetic_companies.py

Idempotent — renamed companies no longer match the placeholder pattern.
"""

from __future__ import annotations

import sys

from playbook_shared.analytics.synthetic import rename_synthetic_companies


def main() -> int:
    renamed = rename_synthetic_companies()
    print(f"Renamed {renamed} synthetic companies to industry-appropriate names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
