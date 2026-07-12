from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.core.config_loader import load_project_config
from pipeline.scouting.schedule import (
    load_schedule,
    summarize_schedule,
    validate_schedule,
    write_schedule_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and summarize a season schedule.")
    parser.add_argument("--org", default="cofc", help="Organization config key.")
    parser.add_argument("--season", default="2026", help="Season label.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_project_config(args.org, args.season, repo_root=REPO_ROOT)
    schedule_path_value = config.season.get("schedule_path")
    if not schedule_path_value:
        raise ValueError(f"No schedule_path configured for {args.org} {args.season}.")

    schedule_path = config.resolve_path(schedule_path_value)
    schedule = load_schedule(schedule_path)
    validation = validate_schedule(schedule, expected_season=config.season_label)
    summary = summarize_schedule(schedule)

    output_dir = config.output_path("schedule_dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_schedule_path = output_dir / "schedule_clean.csv"
    report_path = output_dir / "schedule_qa_report.md"
    summary_path = output_dir / "schedule_summary.json"

    schedule.to_csv(clean_schedule_path, index=False)
    write_schedule_report(schedule, validation, summary, report_path)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "summary": summary,
                "validation": {
                    "ok": validation.ok,
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                },
                "source_file": str(schedule_path.relative_to(config.repo_root)),
            },
            handle,
            indent=2,
        )
        handle.write("\n")

    print(f"Schedule QA {'PASS' if validation.ok else 'FAIL'} for {config.org['short_name']} {config.season_label}")
    print(f"Matches: {summary['matches']}")
    print(f"Date range: {summary['first_match']} to {summary['last_match']}")
    if validation.warnings:
        print(f"Warnings: {len(validation.warnings)}")
    if validation.errors:
        print(f"Errors: {len(validation.errors)}")
    print(f"Outputs: {output_dir}")

    if not validation.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
