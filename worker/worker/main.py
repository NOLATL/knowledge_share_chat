"""Analytics worker entrypoint for on-demand Epic 2 recomputes."""

import sys

from playbook_shared.analytics import recompute


def run() -> int:
    """Run the analytics recompute. Returns the process exit code."""
    summary = recompute()
    print(
        "analytics recompute complete: "
        f"respondents={summary.respondents_processed} "
        f"company_benchmarks={summary.company_benchmarks_written} "
        f"function_grain={summary.function_entities}e/{summary.function_clusters}c/"
        f"{summary.function_silhouette:.3f}s/{summary.function_benchmarks_written}b "
        f"company_grain={summary.company_entities}e/{summary.company_clusters}c/{summary.company_silhouette:.3f}s"
    )
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
