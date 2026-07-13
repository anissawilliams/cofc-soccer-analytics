#!/usr/bin/env python3
"""
Register raw source files in Supabase Storage and public.source_file.

Examples:
    python pipeline/ingestion/register_source_files.py --season 2025 --slug 2025-09-27_william_mary --dry-run
    python pipeline/ingestion/register_source_files.py --season 2025 --slug 2025-09-27_william_mary
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from source_files import WYSCOUT_FILE_KINDS, canonical_wyscout_storage_path
from source_paths import get_source_paths


@dataclass(frozen=True)
class SourceFileCandidate:
    source_system: str
    source_type: str
    file_role: str
    local_path: Path
    storage_path: str
    file_format: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    if path.suffix.lower() == ".xml":
        return "application/xml"
    return "application/octet-stream"


def slug_pdf_key(slug: str) -> str:
    return re.sub(r"[^a-z0-9]", "", slug.lower())


def pdf_key(path: Path) -> str:
    name = path.stem.lower().replace("players_", "")
    return re.sub(r"[^a-z0-9]", "", name)


def find_pdf_for_slug(slug: str) -> Path | None:
    pdf_dir = get_source_paths().wyscout_pdf_dir
    if not pdf_dir.exists():
        return None
    target = slug_pdf_key(slug)
    for path in sorted(pdf_dir.glob("players_*.pdf")):
        if pdf_key(path) == target:
            return path
    return None


def wyscout_candidates(season: str, slug: str, include_pdf: bool = True) -> list[SourceFileCandidate]:
    paths = get_source_paths()
    candidates: list[SourceFileCandidate] = []
    roles = {
        "sportscode": "primary_events",
        "effective_time": "timing",
        "player_events": "supplemental_events",
        "team_events": "team_events",
    }
    for kind, filename_template in WYSCOUT_FILE_KINDS.items():
        local_path = paths.matches_dir / str(season) / slug / filename_template.format(slug=slug)
        if not local_path.exists():
            continue
        candidates.append(SourceFileCandidate(
            source_system="wyscout",
            source_type=kind,
            file_role=roles[kind],
            local_path=local_path,
            storage_path=canonical_wyscout_storage_path(season, slug, kind),
            file_format="xml",
        ))

    if include_pdf:
        pdf_path = find_pdf_for_slug(slug)
        if pdf_path:
            prefix = paths.source_storage_prefix
            storage_path = "/".join(part for part in [
                prefix,
                str(season),
                slug,
                "wyscout",
                "player_report.pdf",
            ] if part)
            candidates.append(SourceFileCandidate(
                source_system="wyscout",
                source_type="pdf_report",
                file_role="validation_report",
                local_path=pdf_path,
                storage_path=storage_path,
                file_format="pdf",
            ))
    return candidates


def manifest_slugs(season: str) -> list[str]:
    manifest_path = get_source_paths().manifest_path
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return sorted(
            row["slug"]
            for row in reader
            if str(row.get("season", "")).strip() == str(season)
            and row.get("slug")
        )


def get_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("Missing package 'supabase'. Install dependencies before registering source files.") from exc

    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def find_session_id(client, season: str, slug: str) -> str | None:
    date = slug[:10]
    try:
        response = (
            client.table("session")
            .select("id")
            .eq("session_date", date)
            .eq("season", str(season))
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    if response.data:
        return response.data[0]["id"]
    return None


def upload_file(client, bucket: str, candidate: SourceFileCandidate) -> None:
    with candidate.local_path.open("rb") as handle:
        client.storage.from_(bucket).upload(
            path=candidate.storage_path,
            file=handle,
            file_options={
                "content-type": content_type_for(candidate.local_path),
                "upsert": "true",
            },
        )


def upsert_source_file(
    client,
    candidate: SourceFileCandidate,
    *,
    season: str,
    slug: str,
    bucket: str,
    session_id: str | None,
    uploaded_by: str,
) -> dict:
    stat = candidate.local_path.stat()
    payload = {
        "session_id": session_id,
        "organization_code": get_source_paths().source_storage_prefix or "cofc",
        "season": str(season),
        "match_slug": slug,
        "source_system": candidate.source_system,
        "source_type": candidate.source_type,
        "file_role": candidate.file_role,
        "storage_bucket": bucket,
        "storage_path": candidate.storage_path,
        "original_filename": candidate.local_path.name,
        "content_type": content_type_for(candidate.local_path),
        "file_format": candidate.file_format,
        "byte_size": stat.st_size,
        "sha256": sha256_file(candidate.local_path),
        "upload_status": "uploaded",
        "parse_status": "pending" if candidate.file_format in {"xml", "csv", "xlsx"} else "not_applicable",
        "uploaded_by": uploaded_by,
        "metadata": {
            "local_path": str(candidate.local_path),
        },
        "is_active": True,
    }
    result = (
        client.table("source_file")
        .upsert(payload, on_conflict="storage_bucket,storage_path")
        .execute()
    )
    return (result.data or [payload])[0]


def register_candidates(
    candidates: list[SourceFileCandidate],
    *,
    season: str,
    slug: str,
    dry_run: bool,
) -> list[dict]:
    paths = get_source_paths()
    rows = []
    if dry_run:
        for candidate in candidates:
            rows.append({
                "source_type": candidate.source_type,
                "local_path": str(candidate.local_path),
                "storage_bucket": paths.source_storage_bucket,
                "storage_path": candidate.storage_path,
                "byte_size": candidate.local_path.stat().st_size,
                "sha256": sha256_file(candidate.local_path),
                "status": "dry_run",
            })
        return rows

    client = get_client()
    session_id = find_session_id(client, season, slug)
    uploaded_by = os.environ.get("USER") or os.environ.get("USERNAME") or "pipeline"

    for candidate in candidates:
        upload_file(client, paths.source_storage_bucket, candidate)
        row = upsert_source_file(
            client,
            candidate,
            season=season,
            slug=slug,
            bucket=paths.source_storage_bucket,
            session_id=session_id,
            uploaded_by=uploaded_by,
        )
        rows.append(row)
    return rows


def print_summary(rows: list[dict], dry_run: bool) -> None:
    label = "DRY RUN" if dry_run else "REGISTERED"
    print(f"\n{label}: {len(rows)} source file(s)")
    for row in rows:
        print(
            f"  - {row.get('source_type')}: "
            f"{row.get('storage_bucket')}/{row.get('storage_path')} "
            f"({row.get('byte_size')} bytes)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload/register raw source files in Supabase Storage and public.source_file")
    parser.add_argument("--season", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Single match slug to register")
    group.add_argument("--all", action="store_true", help="Register all slugs for the season from the manifest")
    parser.add_argument("--source-system", default="wyscout", choices=["wyscout"])
    parser.add_argument("--no-pdf", action="store_true", help="Skip Wyscout PDF report registration")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.source_system != "wyscout":
        raise SystemExit("Only Wyscout source registration is implemented right now.")

    slugs = manifest_slugs(args.season) if args.all else [args.slug]
    all_rows = []
    skipped = []
    for slug in slugs:
        candidates = wyscout_candidates(args.season, slug, include_pdf=not args.no_pdf)
        if not candidates:
            skipped.append(slug)
            continue
        rows = register_candidates(candidates, season=args.season, slug=slug, dry_run=args.dry_run)
        all_rows.extend(rows)

    print_summary(all_rows, args.dry_run)
    if skipped:
        print(f"\nSKIPPED: {len(skipped)} match(es) with no local source files")
        for slug in skipped:
            print(f"  - {slug}")


if __name__ == "__main__":
    main()
