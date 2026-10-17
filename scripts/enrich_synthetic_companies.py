"""CLI: one-off enrichment of legacy synthetic companies for company analytics.

Run locally or as a Railway one-off (needs DATABASE_URL; no OpenAI calls):

    uv run python scripts/enrich_synthetic_companies.py

Assigns realistic industries + firmographics to placeholder-industry synthetic
companies and merges some into multi-respondent companies. Idempotent — a
re-run is a no-op. Run a manual recompute afterwards so peer groups pick up
the new industries.
"""

from __future__ import annotations

import sys

from playbook_shared.analytics.synthetic import enrich_synthetic_companies


def main() -> int:
    result = enrich_synthetic_companies()
    print("Synthetic company enrichment complete:")
    print(f"  enriched: {result.enriched}")
    print(f"  merged:   {result.merged} (into multi-respondent companies)")
    if result.enriched:
        print("Run POST /admin/recompute so peer groups pick up the new industries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
