from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved organization and season config for one pipeline run."""

    repo_root: Path
    org: dict[str, Any]
    season: dict[str, Any]

    @property
    def org_key(self) -> str:
        return str(self.org["org_key"])

    @property
    def season_label(self) -> str:
        return str(self.season["season"])

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.repo_root / path

    def output_path(self, key: str) -> Path:
        outputs = self.season.get("outputs", {})
        if key not in outputs:
            raise KeyError(f"Missing output path '{key}' in season config.")
        return self.resolve_path(outputs[key])


def find_repo_root(start: Path | None = None) -> Path:
    """Find the repository root without relying on the current shell location."""

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "pipeline").exists():
            return candidate
    raise FileNotFoundError(f"Could not find repo root from {current}")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_project_config(
    org_key: str,
    season: str,
    repo_root: Path | None = None,
) -> ProjectConfig:
    root = repo_root or find_repo_root()
    org_path = root / "configs" / "organizations" / f"{org_key}.json"
    season_path = root / "configs" / "seasons" / f"{org_key}_{season}.json"

    if not org_path.exists():
        raise FileNotFoundError(f"Organization config not found: {org_path}")
    if not season_path.exists():
        raise FileNotFoundError(f"Season config not found: {season_path}")

    org = read_json(org_path)
    season_config = read_json(season_path)
    if season_config.get("org_key") != org.get("org_key"):
        raise ValueError(
            f"Config mismatch: {season_path.name} belongs to "
            f"{season_config.get('org_key')}, not {org.get('org_key')}"
        )

    return ProjectConfig(repo_root=root, org=org, season=season_config)
