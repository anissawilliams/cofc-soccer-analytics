from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.core.config_loader import load_project_config
from pipeline.scouting.opponent_shells import write_opponent_shells
from pipeline.scouting.schedule import load_schedule, validate_schedule


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one opposition report shell folder per scheduled match."
    )
    parser.add_argument("--org", default="cofc", help="Organization config key.")
    parser.add_argument("--season", default="2026", help="Season label.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing shell files. By default only missing files are created.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_project_config(args.org, args.season, repo_root=REPO_ROOT)
    schedule_path_value = config.season.get("schedule_path")
    if not schedule_path_value:
        raise ValueError(f"No schedule_path configured for {args.org} {args.season}.")

    schedule = load_schedule(config.resolve_path(schedule_path_value))
    validation = validate_schedule(schedule, expected_season=config.season_label)
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    output_root = config.output_path("scouting_dir") / "opponents"
    paths = write_opponent_shells(
        schedule=schedule,
        output_root=output_root,
        org_short_name=config.org["short_name"],
        force=args.force,
    )

    missing_ids = schedule["opponent_team_id"].astype(str).str.strip().eq("").sum()
    action = "Rebuilt" if args.force else "Ensured"
    print(f"{action} opponent report shells for {config.org['short_name']} {config.season_label}")
    print(f"Matches: {len(paths)}")
    print(f"Missing opponent_team_id: {int(missing_ids)}")
    print(f"Output root: {output_root}")


if __name__ == "__main__":
    main()
