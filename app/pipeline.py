from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


STAGES = [
    ("AI Role Discovery", ["-m", "app.ai.role_discovery"]),
    ("Source Discovery", ["-m", "app.discovery.source_discovery"]),
    ("Source Validation", ["-m", "app.discovery.source_validator"]),
    ("Capability Detection", ["-m", "app.discovery.capability_detector"]),
    ("Search Strategy", ["-m", "app.discovery.search_strategy"]),
    ("Search Execution", ["-m", "app.discovery.search_executor"]),
    ("Source Deduplication", ["-m", "app.discovery.deduplicator"]),
    ("Normalization", ["-m", "app.discovery.normalizer"]),
    ("AI Job Matching", ["-m", "app.ai.job_matcher"]),
    ("Visa Analysis", ["-m", "app.ai.visa_analyzer"]),
    ("Excel Export", ["-m", "app.exporters.excel_exporter"]),
]


def run_stage(
    stage_name: str,
    command: list[str],
) -> None:

    print()
    print("=" * 70)
    print(stage_name)
    print("=" * 70)

    full_command = [
        sys.executable,
        *command,
    ]

    result = subprocess.run(
        full_command,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{stage_name} failed "
            f"with exit code {result.returncode}"
        )


def main() -> None:

    print("=" * 70)
    print("JOBPILOT PIPELINE")
    print("=" * 70)

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Python: {sys.executable}")

    for stage_name, command in STAGES:

        run_stage(
            stage_name,
            command,
        )

    print()
    print("=" * 70)
    print("JOBPILOT PIPELINE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()