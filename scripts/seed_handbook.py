"""CLI to sync the internal handbook corpus into `handbook_chunks` for RAG.

Run locally or as a Railway one-off (needs DATABASE_URL and OPENAI_API_KEY):

    uv run python scripts/seed_handbook.py [--dir knowledge/Playbook_RAG_MDs]

Idempotent: unchanged chunks are skipped (no embedding cost), changed/new chunks
are (re-)embedded, and chunks removed from the corpus are deleted.
"""

from __future__ import annotations

import argparse
import sys

from playbook_shared.handbook import CORPUS_DIR, seed_handbook


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=None, help=f"corpus directory (default: {CORPUS_DIR})")
    args = parser.parse_args()

    try:
        result = seed_handbook(corpus_dir=args.dir)
    except FileNotFoundError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print("Handbook corpus synced:")
    print(f"  embedded: {len(result.embedded)}")
    print(f"  skipped:  {len(result.skipped)} (unchanged)")
    print(f"  deleted:  {len(result.deleted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
