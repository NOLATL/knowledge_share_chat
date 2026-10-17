"""Seed synthetic respondents for Epic 2."""

from __future__ import annotations

import argparse

from playbook_shared.analytics.synthetic import SyntheticProgress, seed_synthetic_respondents


def _print_progress(progress: SyntheticProgress) -> None:
    position = f"{progress.index + 1}/{progress.total}"
    message = f" {progress.message}" if progress.message else ""
    print(f"[synthetic] {position} {progress.status} model={progress.model}{message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--deterministic", action="store_true")
    args = parser.parse_args()

    summary = seed_synthetic_respondents(
        count=args.count,
        seed=args.seed,
        use_llm=not args.deterministic,
        progress_callback=_print_progress,
    )
    print(
        f"requested={summary.requested} created={summary.created} "
        f"skipped_existing={summary.skipped_existing} model={summary.model}"
    )


if __name__ == "__main__":
    main()
