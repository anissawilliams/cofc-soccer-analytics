from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[2]
INGESTION_DIR = ROOT / "pipeline" / "ingestion"
MIGRATION_PATH = ROOT / "schema" / "2026_07_metric_scoring_rule.sql"
sys.path.insert(0, str(INGESTION_DIR))

from load_match import WYSCOUT_SCORABLE_LABELS  # noqa: E402


def parse_seed_pairs(sql: str) -> list[tuple[str, str]]:
    seed = sql.split("WITH rule_seed", 1)[1].split(")\nINSERT INTO", 1)[0]
    return re.findall(
        r"^\s*\('([^'\n]+)',\s*'([^'\n]+)'",
        seed,
        flags=re.MULTILINE,
    )


def validate(*, check_live: bool) -> list[str]:
    pairs = parse_seed_pairs(MIGRATION_PATH.read_text())
    metric_names = {metric_name for metric_name, _ in pairs}
    source_labels = {source_label for _, source_label in pairs}
    expected_labels = set(WYSCOUT_SCORABLE_LABELS)
    errors = []

    if len(pairs) != len(expected_labels):
        errors.append(
            f"Expected {len(expected_labels)} seed rows; found {len(pairs)}."
        )
    missing_labels = sorted(expected_labels - source_labels)
    extra_labels = sorted(source_labels - expected_labels)
    if missing_labels:
        errors.append(f"Missing source labels: {missing_labels}")
    if extra_labels:
        errors.append(f"Unexpected source labels: {extra_labels}")

    if check_live:
        load_dotenv(ROOT / ".env")
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            errors.append("SUPABASE_URL and SUPABASE_SERVICE_KEY are required.")
        else:
            client = create_client(url, key)
            rows = client.table("metric_definition").select(
                "name"
            ).execute().data or []
            live_names = {row["name"] for row in rows}
            missing_metrics = sorted(metric_names - live_names)
            if missing_metrics:
                errors.append(f"Seed metrics missing from Supabase: {missing_metrics}")
            try:
                rule_result = client.table("metric_scoring_rule").select(
                    "source_event_label", count="exact"
                ).eq("is_active", True).is_("effective_to", "null").execute()
                live_labels = {
                    row["source_event_label"] for row in (rule_result.data or [])
                }
                missing_live_labels = sorted(expected_labels - live_labels)
                if missing_live_labels:
                    errors.append(
                        "Active scoring rules missing from Supabase: "
                        f"{missing_live_labels}"
                    )
                if rule_result.count != len(expected_labels):
                    errors.append(
                        "Expected "
                        f"{len(expected_labels)} active live rules; found "
                        f"{rule_result.count or 0}."
                    )
            except Exception as exc:
                errors.append(
                    "Supabase metric_scoring_rule is unavailable; migration is "
                    f"probably not applied: {exc}"
                )

    print(
        f"Scoring metadata migration: {len(pairs)} seed rows, "
        f"{len(source_labels)} unique source labels."
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate normalized scoring metadata before migration."
    )
    parser.add_argument(
        "--check-live",
        action="store_true",
        help="Also confirm every seeded metric exists in Supabase.",
    )
    args = parser.parse_args()
    errors = validate(check_live=args.check_live)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Scoring metadata migration validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
