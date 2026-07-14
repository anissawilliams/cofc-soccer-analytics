from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_CONFIG = REPO_ROOT / "configs" / "organizations" / "cofc_recruiting.json"
DEFAULT_SCHEMA = REPO_ROOT / "pipeline" / "config" / "recruiting_player_profile_schema.csv"
DEFAULT_INTERNAL = REPO_ROOT / "pipeline" / "data" / "recruiting" / "internal_player_profiles.csv"
DEFAULT_RECRUITS = REPO_ROOT / "pipeline" / "data" / "recruiting" / "recruit_player_profiles.csv"
DEFAULT_OUTPUT = REPO_ROOT / "pipeline" / "outputs" / "reports" / "recruiting" / "2026" / "recruiting_readiness_report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build recruiting/player-similarity readiness report.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--internal-profiles", type=Path, default=DEFAULT_INTERNAL)
    parser.add_argument("--recruit-profiles", type=Path, default=DEFAULT_RECRUITS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = read_json(args.config)
    schema = read_schema(args.schema)

    internal = assess_profile_file(
        path=args.internal_profiles,
        schema=schema,
        profile_type="internal CofC profiles",
        minimum_minutes=int(config["minimum_minutes"]["internal_profile"]),
    )
    recruits = assess_profile_file(
        path=args.recruit_profiles,
        schema=schema,
        profile_type="recruit profiles",
        minimum_minutes=int(config["minimum_minutes"]["recruit_profile"]),
    )
    config_assessment = assess_config(config)

    blocking = (
        config_assessment["blocking_errors"]
        + internal["blocking_errors"]
        + recruits["blocking_errors"]
    )
    warnings = (
        config_assessment["warnings"]
        + internal["warnings"]
        + recruits["warnings"]
    )
    status = "READY"
    if blocking:
        status = "BLOCKED"
    elif warnings:
        status = "CAUTION"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_markdown(
            config=config,
            config_path=args.config,
            schema_path=args.schema,
            internal=internal,
            recruits=recruits,
            config_assessment=config_assessment,
            status=status,
            blocking=blocking,
            warnings=warnings,
        ),
        encoding="utf-8",
    )

    print(f"Recruiting readiness: {status}")
    print(f"Internal profiles: {internal['rows']} rows")
    print(f"Recruit profiles: {recruits['rows']} rows")
    print(f"Wrote {args.output}")
    if status == "BLOCKED":
        raise SystemExit(1)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_schema(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    return pd.read_csv(path)


def assess_config(config: dict) -> dict[str, object]:
    required_top = ["position_groups", "feature_groups", "position_feature_weights", "minimum_minutes", "similarity"]
    blocking: list[str] = []
    warnings: list[str] = []
    for key in required_top:
        if key not in config:
            blocking.append(f"Recruiting config missing `{key}`.")
    if blocking:
        return {"blocking_errors": blocking, "warnings": warnings}

    position_groups = set(config["position_groups"])
    weighted_groups = set(config["position_feature_weights"])
    missing_weights = sorted(position_groups.difference(weighted_groups))
    if missing_weights:
        blocking.append(f"Missing position_feature_weights for: {missing_weights}")

    feature_groups = set(config["feature_groups"])
    for position_group, weights in config["position_feature_weights"].items():
        unknown_groups = sorted(set(weights).difference(feature_groups))
        if unknown_groups:
            blocking.append(f"{position_group} weights reference unknown feature groups: {unknown_groups}")
        total_weight = sum(float(value) for value in weights.values())
        if abs(total_weight - 1.0) > 1e-6:
            warnings.append(f"{position_group} feature-group weights sum to {total_weight:.3f}, not 1.0.")

    return {"blocking_errors": blocking, "warnings": warnings}


def assess_profile_file(path: Path, schema: pd.DataFrame, profile_type: str, minimum_minutes: int) -> dict[str, object]:
    required_columns = schema.loc[schema["required"].astype(str).str.lower().eq("true"), "column"].tolist()
    result = {
        "profile_type": profile_type,
        "path": str(path.relative_to(REPO_ROOT)) if path.is_absolute() and path.is_relative_to(REPO_ROOT) else str(path),
        "exists": path.exists(),
        "rows": 0,
        "eligible_rows": 0,
        "position_group_counts": {},
        "missing_required_columns": [],
        "blocking_errors": [],
        "warnings": [],
    }
    if not path.exists():
        result["blocking_errors"].append(f"Missing {profile_type} file: {result['path']}")
        return result

    df = pd.read_csv(path)
    result["rows"] = int(len(df))
    missing_columns = [column for column in required_columns if column not in df.columns]
    result["missing_required_columns"] = missing_columns
    if missing_columns:
        result["blocking_errors"].append(f"{profile_type} missing required columns: {missing_columns}")
        return result

    minutes = pd.to_numeric(df["minutes"], errors="coerce").fillna(0)
    eligible = df[minutes >= minimum_minutes].copy()
    result["eligible_rows"] = int(len(eligible))
    result["position_group_counts"] = {
        str(group): int(count)
        for group, count in eligible["position_group"].value_counts().sort_index().items()
    }
    if df.empty:
        result["blocking_errors"].append(f"{profile_type} file has no rows.")
    if eligible.empty:
        result["warnings"].append(
            f"{profile_type} has no rows meeting the {minimum_minutes}-minute threshold."
        )
    return result


def build_markdown(
    config: dict,
    config_path: Path,
    schema_path: Path,
    internal: dict,
    recruits: dict,
    config_assessment: dict,
    status: str,
    blocking: list[str],
    warnings: list[str],
) -> str:
    lines = [
        "# Recruiting Similarity Readiness Report",
        "",
        f"Program: {config.get('program_name', '')}",
        f"Active season: `{config.get('active_season', '')}`",
        "",
        "## Status",
        "",
        f"- Status: `{status}`",
        f"- Blocking errors: `{len(blocking)}`",
        f"- Warnings: `{len(warnings)}`",
        "",
        "## Config",
        "",
        f"- Config: `{relative(config_path)}`",
        f"- Schema: `{relative(schema_path)}`",
        f"- Similarity method: `{config.get('similarity', {}).get('method', '')}`",
        f"- Normalization: `{config.get('similarity', {}).get('normalization', '')}`",
        f"- Position groups: `{list(config.get('position_groups', {}).keys())}`",
        "",
        "## Profile Inputs",
        "",
        profile_table([internal, recruits]),
        "",
        "## Blocking Errors",
        "",
        *format_list(blocking),
        "",
        "## Warnings",
        "",
        *format_list(warnings),
        "",
        "## Interpretation",
        "",
        "- `BLOCKED` is expected until internal and recruit profile CSVs exist.",
        "- This lane is designed for unsupervised similarity, comps, and shortlist generation.",
        "- COUG-derived features should be added only after 2026 scoring provenance is stable.",
        "",
    ]
    if config_assessment["blocking_errors"] or config_assessment["warnings"]:
        lines.extend([
            "## Config Findings",
            "",
            *format_list(config_assessment["blocking_errors"] + config_assessment["warnings"]),
            "",
        ])
    return "\n".join(lines)


def profile_table(profiles: list[dict]) -> str:
    lines = [
        "| profile_type | path | exists | rows | eligible_rows | position_group_counts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for profile in profiles:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(profile["profile_type"]),
                    f"`{profile['path']}`",
                    str(profile["exists"]),
                    str(profile["rows"]),
                    str(profile["eligible_rows"]),
                    f"`{profile['position_group_counts']}`",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def format_list(values: list[str]) -> list[str]:
    if not values:
        return ["_None._"]
    return [f"- {value}" for value in values]


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
