#!/usr/bin/env python3
"""Validate a staff event CSV independently of the Wyscout match parser."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_match_intake import write_rows
from staff_events import inspect_staff_events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--staff-dir", type=Path, required=True)
    parser.add_argument("--roster", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    staff_dir = args.staff_dir.resolve()
    source_path = staff_dir / "staff_events.csv"
    roster_path = (
        args.roster
        or Path(__file__).resolve().parent / f"roster_{args.season}.csv"
    ).resolve()
    status, events = inspect_staff_events(
        source_path,
        roster_path,
        slug=args.slug,
        season=str(args.season),
    )
    report = {"slug": args.slug, "season": str(args.season), "staff_events": status}
    print(json.dumps(report, indent=2, sort_keys=True))
    if not status["ready"] or not status["supplied"]:
        raise SystemExit(2)
    if args.dry_run:
        return

    output_dir = (args.output_dir or staff_dir.parent / "20_generated").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_rows(output_dir / f"{args.slug}_staff_events.csv", events)
    (output_dir / f"{args.slug}_staff_events_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Prepared staff events: {output_dir}")


if __name__ == "__main__":
    main()
