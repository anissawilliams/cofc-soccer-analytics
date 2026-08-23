#!/usr/bin/env python3
"""Promote a staff-approved match intake bundle to Supabase.

The command is dry-run-first: no remote client is created unless ``--apply`` is
present. Raw vendor files and approved generated artifacts are stored under
content-addressed paths and registered in ``public.source_file``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from source_paths import get_source_paths


APPROVAL_VERSION = 1
APPROVAL_KEYS = ("source_archive", "match_analytics", "coug_scoring")
PROFILE_TYPES = {
    "scoring_event_xml": "sportscode",
    "player_event_xml": "player_events",
    "team_event_xml": "team_events",
    "effective_time_xml": "effective_time",
    "invalid_xml": "xml",
    "unknown_xml": "xml",
}
GENERATED_ARTIFACTS = {
    "metadata.json": ("review_bundle", "match_metadata", "review_metadata"),
    "intake_report.json": ("review_bundle", "intake_report", "validation_report"),
    "validation_report.md": ("review_bundle", "validation_report", "validation_report"),
    "approval.json": ("review_bundle", "staff_approval", "approval_record"),
    "canonical_team_events.csv": ("match_analytics", "canonical_team_events", "primary_events"),
    "match_flow.json": ("match_analytics", "match_flow", "dashboard_snapshot"),
    "players.csv": ("coug_scoring", "player_events", "scoring_input"),
    "all_player_events.csv": ("coug_scoring", "all_player_events", "qa_stream"),
    "sportscode_team_events.csv": ("coug_scoring", "sportscode_team_events", "qa_stream"),
    "minutes.csv": ("coug_scoring", "official_minutes", "scoring_input"),
}


class PromotionError(ValueError):
    """Raised when a bundle is unsafe or not approved for promotion."""


@dataclass(frozen=True)
class PromotionCandidate:
    local_path: Path
    relative_path: str
    source_system: str
    source_type: str
    file_role: str
    product: str
    sha256: str
    byte_size: int
    storage_path: str
    metadata: dict


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_filename(name: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._")
    return stem or "source_file"


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return "application/octet-stream"


def source_system_for(relative_path: str) -> str:
    parts = {part.lower() for part in Path(relative_path).parts}
    if "spiideo" in parts:
        return "spiideo"
    if "wyscout" in parts or Path(relative_path).suffix.lower() == ".xml":
        return "wyscout"
    return "manual"


def storage_path_for(
    *, prefix: str, season: str, slug: str, area: str, source_system: str,
    source_type: str, digest: str, filename: str,
) -> str:
    parts = [
        prefix.strip("/"), str(season), slug, area, source_system, source_type,
        f"{digest[:12]}_{safe_filename(filename)}",
    ]
    return "/".join(part for part in parts if part)


def load_json_object(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError(f"Could not read {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PromotionError(f"{label} must contain a JSON object: {path}")
    return payload


def validate_approval(approval: dict, report: dict, report_path: Path) -> dict[str, bool]:
    if approval.get("schema_version") != APPROVAL_VERSION:
        raise PromotionError(f"Approval schema_version must be {APPROVAL_VERSION}.")
    if approval.get("match_slug") != report.get("slug"):
        raise PromotionError("Approval match_slug does not match the intake report.")
    if str(approval.get("season")) != str(report.get("season")):
        raise PromotionError("Approval season does not match the intake report.")
    if approval.get("intake_report_sha256") != sha256_file(report_path):
        raise PromotionError("The intake report changed after approval; review it again.")
    if not str(approval.get("reviewed_by") or "").strip():
        raise PromotionError("Approval reviewed_by is required.")
    try:
        reviewed_at = datetime.fromisoformat(str(approval.get("reviewed_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise PromotionError("Approval reviewed_at must be an ISO-8601 timestamp.") from exc
    if reviewed_at.tzinfo is None:
        raise PromotionError("Approval reviewed_at must include a timezone.")

    approvals = approval.get("approvals")
    if not isinstance(approvals, dict) or any(type(approvals.get(key)) is not bool for key in APPROVAL_KEYS):
        raise PromotionError(f"Approval must contain boolean values for: {', '.join(APPROVAL_KEYS)}.")
    if not any(approvals[key] for key in APPROVAL_KEYS):
        raise PromotionError("Nothing is approved for promotion.")
    if approvals["match_analytics"] and not report.get("analytics", {}).get("ready"):
        raise PromotionError("Match analytics were approved, but the intake report says they are not ready.")
    if approvals["coug_scoring"] and not report.get("scoring", {}).get("ready"):
        raise PromotionError("COUG scoring was approved, but the intake report says it is not ready.")
    if approvals["coug_scoring"] and not report.get("minutes", {}).get("ready"):
        raise PromotionError(
            "COUG scoring was approved, but official minutes and starters are not ready."
        )
    if report.get("validation", {}).get("status") == "blocked":
        raise PromotionError("Blocked intake bundles cannot be promoted.")
    return {key: approvals[key] for key in APPROVAL_KEYS}


def verify_source_manifest(source_dir: Path, report: dict) -> dict[str, dict]:
    manifest = report.get("source_manifest")
    if not isinstance(manifest, list) or not manifest:
        raise PromotionError("The intake report has no source manifest.")
    verified = {}
    for item in manifest:
        relative_path = str(item.get("relative_path") or "")
        path = (source_dir / relative_path).resolve()
        if not relative_path or source_dir.resolve() not in path.parents:
            raise PromotionError(f"Unsafe source manifest path: {relative_path!r}")
        if not path.is_file():
            raise PromotionError(f"Source file is missing: {relative_path}")
        digest = sha256_file(path)
        if digest != item.get("sha256") or path.stat().st_size != item.get("size_bytes"):
            raise PromotionError(f"Source file changed after intake: {relative_path}")
        verified[relative_path] = {**item, "path": path, "sha256": digest}
    return verified


def build_candidates(
    source_dir: Path, bundle_dir: Path, report: dict, approvals: dict[str, bool],
    *, prefix: str,
) -> list[PromotionCandidate]:
    season = str(report["season"])
    slug = str(report["slug"])
    source_manifest = verify_source_manifest(source_dir, report)
    profiles = {str(row.get("relative_path")): row for row in report.get("files", [])}
    candidates: list[PromotionCandidate] = []

    required_suffixes = {"metadata.json", "intake_report.json", "validation_report.md", "approval.json"}
    if approvals["match_analytics"]:
        required_suffixes.update({"canonical_team_events.csv", "match_flow.json"})
    if approvals["coug_scoring"]:
        required_suffixes.update({
            "players.csv", "all_player_events.csv", "sportscode_team_events.csv", "minutes.csv"
        })
    missing = [suffix for suffix in sorted(required_suffixes) if not (bundle_dir / f"{slug}_{suffix}").is_file()]
    if missing:
        raise PromotionError(f"Approved review bundle is missing: {', '.join(missing)}")

    if approvals["source_archive"]:
        for relative_path, item in source_manifest.items():
            path = item["path"]
            profile = profiles.get(relative_path, {})
            source_type = PROFILE_TYPES.get(profile.get("kind"), path.suffix.lower().lstrip(".") or "file")
            system = source_system_for(relative_path)
            digest = item["sha256"]
            candidates.append(PromotionCandidate(
                local_path=path,
                relative_path=relative_path,
                source_system=system,
                source_type=source_type,
                file_role="primary_events" if profile.get("kind") not in {"invalid_xml", "unknown_xml"} else "other",
                product="source_archive",
                sha256=digest,
                byte_size=path.stat().st_size,
                storage_path=storage_path_for(
                    prefix=prefix, season=season, slug=slug, area="raw",
                    source_system=system, source_type=source_type, digest=digest,
                    filename=path.name,
                ),
                metadata={
                    "source_relative_path": relative_path,
                    "detected_kind": profile.get("kind"),
                    "detected_team": profile.get("team"),
                    "intake_product": "source_archive",
                },
            ))

    for suffix, (product, source_type, role) in GENERATED_ARTIFACTS.items():
        approved = product == "review_bundle" or approvals.get(product, False)
        path = bundle_dir / f"{slug}_{suffix}"
        if not approved or not path.is_file():
            continue
        digest = sha256_file(path)
        candidates.append(PromotionCandidate(
            local_path=path,
            relative_path=path.name,
            source_system="pipeline",
            source_type=source_type,
            file_role=role,
            product=product,
            sha256=digest,
            byte_size=path.stat().st_size,
            storage_path=storage_path_for(
                prefix=prefix, season=season, slug=slug, area="generated",
                source_system="pipeline", source_type=source_type, digest=digest,
                filename=path.name,
            ),
            metadata={"intake_product": product},
        ))
    return candidates


def get_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("Missing package 'supabase'. Install project dependencies first.") from exc
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def find_session_id(client, season: str, slug: str) -> str | None:
    result = (
        client.table("session").select("id").eq("session_date", slug[:10])
        .eq("season", str(season)).limit(2).execute()
    )
    rows = result.data or []
    if len(rows) > 1:
        raise PromotionError(f"More than one {season} session exists on {slug[:10]}; resolve it before promotion.")
    return rows[0]["id"] if rows else None


def row_payload(candidate: PromotionCandidate, report: dict, approval: dict, bucket: str, session_id: str | None) -> dict:
    parse_status = "parsed" if candidate.product != "source_archive" or candidate.metadata.get("detected_kind") not in {"invalid_xml", "unknown_xml", None} else "pending"
    return {
        "session_id": session_id,
        "organization_code": get_source_paths().source_storage_prefix or "cofc",
        "season": str(report["season"]),
        "match_slug": report["slug"],
        "source_system": candidate.source_system,
        "source_type": candidate.source_type,
        "file_role": candidate.file_role,
        "storage_bucket": bucket,
        "storage_path": candidate.storage_path,
        "original_filename": candidate.local_path.name,
        "content_type": content_type_for(candidate.local_path),
        "file_format": candidate.local_path.suffix.lower().lstrip("."),
        "byte_size": candidate.byte_size,
        "sha256": candidate.sha256,
        "upload_status": "uploaded",
        "parse_status": parse_status,
        "parser_version": "match_intake_v1",
        "uploaded_by": approval["reviewed_by"],
        "metadata": {
            **candidate.metadata,
            "reviewed_by": approval["reviewed_by"],
            "reviewed_at": approval["reviewed_at"],
            "approval_notes": approval.get("notes", ""),
        },
        "is_active": True,
    }


def apply_candidates(client, candidates: list[PromotionCandidate], report: dict, approval: dict, bucket: str) -> list[dict]:
    # Fail before uploading if the required migration/table is not available.
    client.table("source_file").select("id").limit(1).execute()
    session_id = find_session_id(client, str(report["season"]), str(report["slug"]))
    receipt = []
    for candidate in candidates:
        with candidate.local_path.open("rb") as handle:
            client.storage.from_(bucket).upload(
                path=candidate.storage_path,
                file=handle,
                file_options={"content-type": content_type_for(candidate.local_path), "upsert": "true"},
            )
        payload = row_payload(candidate, report, approval, bucket, session_id)
        result = client.table("source_file").upsert(
            payload, on_conflict="storage_bucket,storage_path"
        ).execute()
        receipt.append((result.data or [payload])[0])
    return receipt


def write_receipt(bundle_dir: Path, report: dict, approval: dict, rows: list[dict], *, applied: bool) -> Path:
    payload = {
        "schema_version": 1,
        "match_slug": report["slug"],
        "season": str(report["season"]),
        "mode": "applied" if applied else "dry_run",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": approval["reviewed_by"],
        "approvals": approval["approvals"],
        "session_id": next((row.get("session_id") for row in rows if row.get("session_id")), None),
        "objects": rows,
    }
    name = f"{report['slug']}_promotion_receipt.json"
    path = bundle_dir / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--approval", type=Path, default=None, help="Defaults to <slug>_approval.json in the bundle")
    parser.add_argument("--apply", action="store_true", help="Write to Supabase; omission is a dry run")
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser().resolve()
    bundle_dir = args.bundle_dir.expanduser().resolve()
    reports = sorted(bundle_dir.glob("*_intake_report.json"))
    if len(reports) != 1:
        raise PromotionError(f"Expected exactly one intake report in {bundle_dir}; found {len(reports)}.")
    report_path = reports[0]
    report = load_json_object(report_path, "intake report")
    approval_path = (args.approval or bundle_dir / f"{report['slug']}_approval.json").expanduser().resolve()
    approval = load_json_object(approval_path, "staff approval")
    approvals = validate_approval(approval, report, report_path)
    paths = get_source_paths()
    candidates = build_candidates(source_dir, bundle_dir, report, approvals, prefix=paths.source_storage_prefix)
    if not candidates:
        raise PromotionError("No approved files were found to promote.")

    if args.apply:
        rows = apply_candidates(get_client(), candidates, report, approval, paths.source_storage_bucket)
    else:
        rows = [
            {
                "source_type": item.source_type,
                "product": item.product,
                "original_filename": item.local_path.name,
                "storage_bucket": paths.source_storage_bucket,
                "storage_path": item.storage_path,
                "byte_size": item.byte_size,
                "sha256": item.sha256,
                "status": "dry_run",
            }
            for item in candidates
        ]
    receipt = write_receipt(bundle_dir, report, approval, rows, applied=args.apply)
    print(f"{'PROMOTED' if args.apply else 'DRY RUN'}: {len(rows)} file(s)")
    for row in rows:
        print(f"  - {row.get('source_type')}: {row.get('storage_bucket')}/{row.get('storage_path')}")
    if args.apply and not any(row.get("session_id") for row in rows):
        print("WARNING: no matching session exists yet; source files were registered without session_id.")
    print(f"Receipt: {receipt}")


if __name__ == "__main__":
    main()
