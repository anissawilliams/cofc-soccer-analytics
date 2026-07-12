"""
source_paths.py
===============
Single source of truth for local soccer analytics source/output paths.

The pipeline currently has real 2025 Wyscout XML and Wyscout PDF reports.
Spiideo is intentionally modeled as a future/optional source: its folders can
exist, but Wyscout-only 2025 ingestion must not fail just because Spiideo is
missing.

Override any path with an environment variable when running outside the repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourcePaths:
    repo_root: Path
    pipeline_root: Path
    matches_dir: Path
    raw_dir: Path
    wyscout_pdf_dir: Path
    parsed_outputs_dir: Path
    legacy_data_outputs_dir: Path
    manifests_dir: Path
    manifest_path: Path
    reports_dir: Path
    roster_path: Path
    future_spiideo_dir: Path


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def get_source_paths() -> SourcePaths:
    repo_root = _env_path("COFC_REPO_ROOT", repo_root_from_here())
    pipeline_root = _env_path("COFC_PIPELINE_ROOT", repo_root / "pipeline")

    matches_dir = _env_path("COFC_MATCHES_DIR", pipeline_root / "data" / "matches")
    raw_dir = _env_path("COFC_RAW_DIR", pipeline_root / "data" / "raw")
    wyscout_pdf_dir = _env_path("COFC_WYSCOUT_PDF_DIR", raw_dir / "player_reports")

    # Canonical parsed output location. pipeline/data/outputs is legacy and
    # still reported by inventory commands so old files do not disappear.
    parsed_outputs_dir = _env_path("COFC_PARSED_OUTPUTS_DIR", pipeline_root / "outputs")
    legacy_data_outputs_dir = _env_path("COFC_LEGACY_DATA_OUTPUTS_DIR", pipeline_root / "data" / "outputs")

    manifests_dir = _env_path("COFC_MANIFESTS_DIR", pipeline_root / "data" / "manifests")
    manifest_path = _env_path("COFC_MATCHES_MANIFEST", manifests_dir / "matches_manifest.csv")
    reports_dir = _env_path("COFC_REPORTS_DIR", pipeline_root / "outputs" / "reports")
    roster_path = _env_path("COFC_ROSTER_PATH", pipeline_root / "ingestion" / "roster_2025.csv")
    future_spiideo_dir = _env_path("COFC_SPIIDEO_DIR", raw_dir / "spiideo")

    return SourcePaths(
        repo_root=repo_root,
        pipeline_root=pipeline_root,
        matches_dir=matches_dir,
        raw_dir=raw_dir,
        wyscout_pdf_dir=wyscout_pdf_dir,
        parsed_outputs_dir=parsed_outputs_dir,
        legacy_data_outputs_dir=legacy_data_outputs_dir,
        manifests_dir=manifests_dir,
        manifest_path=manifest_path,
        reports_dir=reports_dir,
        roster_path=roster_path,
        future_spiideo_dir=future_spiideo_dir,
    )


def match_dir_for(season: str, slug: str) -> Path:
    return get_source_paths().matches_dir / str(season) / slug


def parsed_output_dir_for(season: str, slug: str) -> Path:
    return get_source_paths().parsed_outputs_dir / str(season) / slug
