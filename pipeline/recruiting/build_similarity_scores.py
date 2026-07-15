"""Build player similarity scores for CofC recruiting.

This script compares recruit profiles against:
  1. An ideal profile built from eligible internal CofC players per position group.
  2. Individual internal CofC players (nearest-comp matching).

Outputs:
  position_ideal_profiles.csv      — one row per position group, mean feature values
  recruit_similarity_scores.csv    — recruits ranked by similarity to ideal profile
  recruit_feature_gaps.csv         — per-recruit feature deltas vs ideal profile
  nearest_cofc_comps.csv           — top-N internal comps per recruit
  shortlist_<position_group>.md    — coach-facing shortlist per position group

When recruit_player_profiles.csv is absent or empty, the script runs in
internal-only mode and produces internal_similarity_scores.csv (each CofC
player scored against the ideal profile for their position group) plus
nearest_cofc_comps.csv showing player-to-player comps within the roster.
This lets the pipeline be validated before recruit data arrives.

Usage
-----
    python pipeline/recruiting/build_similarity_scores.py --season 2025

    # Internal-only mode (no recruit profiles needed)
    python pipeline/recruiting/build_similarity_scores.py --season 2025 --internal-only
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG = REPO_ROOT / "configs" / "organizations" / "cofc_recruiting.json"
DEFAULT_SCHEMA = REPO_ROOT / "pipeline" / "config" / "recruiting_player_profile_schema.csv"
DEFAULT_INTERNAL = REPO_ROOT / "pipeline" / "data" / "recruiting" / "internal_player_profiles.csv"
DEFAULT_RECRUITS = REPO_ROOT / "pipeline" / "data" / "recruiting" / "recruit_player_profiles.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "pipeline" / "outputs" / "reports" / "recruiting" / "2026"

# Features that are excluded from similarity computation (identity / metadata)
IDENTITY_COLS = {
    "player_id", "player_name", "source_system", "source_file", "season",
    "team", "competition", "country", "date_of_birth", "age",
    "primary_position", "secondary_positions", "position_group",
    "dominant_foot", "height_cm", "minutes", "matches", "notes",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build CofC recruiting player similarity scores."
    )
    parser.add_argument("--season", default="2025", help="Season label for report headers.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--internal-profiles", type=Path, default=DEFAULT_INTERNAL)
    parser.add_argument("--recruit-profiles", type=Path, default=DEFAULT_RECRUITS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--internal-only",
        action="store_true",
        help="Run in internal-only mode even if recruit profiles exist.",
    )
    parser.add_argument(
        "--position-group",
        default=None,
        help="Limit run to one position group (e.g. CB, ST).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    config = read_json(args.config)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    internal_df = load_profiles(args.internal_profiles, label="internal")
    recruit_df = load_profiles(args.recruit_profiles, label="recruit") if not args.internal_only else pd.DataFrame()

    internal_only_mode = recruit_df.empty

    if internal_only_mode:
        print("Running in internal-only mode (no recruit profiles found).")

    # Filter by minutes thresholds
    internal_min = int(config["minimum_minutes"]["internal_profile"])
    recruit_min = int(config["minimum_minutes"]["recruit_profile"])

    internal_eligible = filter_by_minutes(internal_df, internal_min, label="internal")
    recruit_eligible = filter_by_minutes(recruit_df, recruit_min, label="recruit") if not internal_only_mode else pd.DataFrame()

    # Limit to one position group if requested
    if args.position_group:
        internal_eligible = internal_eligible[
            internal_eligible["position_group"].eq(args.position_group)
        ].copy()
        if not recruit_eligible.empty:
            recruit_eligible = recruit_eligible[
                recruit_eligible["position_group"].eq(args.position_group)
            ].copy()

    position_groups = sorted(config["position_groups"].keys())
    feature_groups = config["feature_groups"]
    position_weights = config["position_feature_weights"]
    top_n_comps = int(config["similarity"].get("top_n_comps", 5))
    top_n_shortlist = int(config["similarity"].get("top_n_shortlist", 25))

    # Collect all feature columns (ordered, deduped)
    all_feature_cols = ordered_feature_cols(feature_groups)

    # Build ideal profiles per position group
    ideal_profiles = build_ideal_profiles(internal_eligible, position_groups, all_feature_cols)
    save_ideal_profiles(ideal_profiles, output_dir)

    if internal_only_mode:
        # Score internal players using leave-one-out ideal profiles so each
        # player is scored against the mean of their peers (not themselves),
        # producing meaningful differentiation within the group.
        loo_ideal_profiles = build_loo_ideal_profiles(internal_eligible, position_groups, all_feature_cols)
        similarity_df = score_against_ideal(
            candidates=internal_eligible,
            ideal_profiles=loo_ideal_profiles,
            position_groups=position_groups,
            feature_groups=feature_groups,
            position_weights=position_weights,
            all_feature_cols=all_feature_cols,
        )
        gaps_df = compute_feature_gaps(
            candidates=internal_eligible,
            ideal_profiles=ideal_profiles,  # use full ideal for gap display
            position_groups=position_groups,
            all_feature_cols=all_feature_cols,
        )
        comps_df = compute_internal_comps(
            candidates=internal_eligible,
            internal=internal_eligible,
            position_groups=position_groups,
            feature_groups=feature_groups,
            position_weights=position_weights,
            all_feature_cols=all_feature_cols,
            top_n=top_n_comps,
            self_comp=False,
        )

        similarity_df.to_csv(output_dir / "internal_similarity_scores.csv", index=False)
        gaps_df.to_csv(output_dir / "internal_feature_gaps.csv", index=False)
        comps_df.to_csv(output_dir / "nearest_cofc_comps.csv", index=False)

        build_shortlist_reports(
            similarity_df=similarity_df,
            gaps_df=gaps_df,
            comps_df=comps_df,
            position_groups=position_groups,
            output_dir=output_dir,
            season=args.season,
            top_n=top_n_shortlist,
            internal_only=True,
        )

        print(f"Internal-only run complete.")
        print(f"  Eligible internal players : {len(internal_eligible)}")
        print(f"  Position groups           : {list(ideal_profiles.keys())}")
        print(f"  Outputs                   : {output_dir}")

    else:
        similarity_df = score_against_ideal(
            candidates=recruit_eligible,
            ideal_profiles=ideal_profiles,
            position_groups=position_groups,
            feature_groups=feature_groups,
            position_weights=position_weights,
            all_feature_cols=all_feature_cols,
        )
        gaps_df = compute_feature_gaps(
            candidates=recruit_eligible,
            ideal_profiles=ideal_profiles,
            position_groups=position_groups,
            all_feature_cols=all_feature_cols,
        )
        comps_df = compute_internal_comps(
            candidates=recruit_eligible,
            internal=internal_eligible,
            position_groups=position_groups,
            feature_groups=feature_groups,
            position_weights=position_weights,
            all_feature_cols=all_feature_cols,
            top_n=top_n_comps,
            self_comp=True,
        )

        similarity_df.to_csv(output_dir / "recruit_similarity_scores.csv", index=False)
        gaps_df.to_csv(output_dir / "recruit_feature_gaps.csv", index=False)
        comps_df.to_csv(output_dir / "nearest_cofc_comps.csv", index=False)

        build_shortlist_reports(
            similarity_df=similarity_df,
            gaps_df=gaps_df,
            comps_df=comps_df,
            position_groups=position_groups,
            output_dir=output_dir,
            season=args.season,
            top_n=top_n_shortlist,
            internal_only=False,
        )

        print(f"Similarity scoring complete.")
        print(f"  Eligible internal players : {len(internal_eligible)}")
        print(f"  Eligible recruits         : {len(recruit_eligible)}")
        print(f"  Outputs                   : {output_dir}")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_profiles(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    if df.empty:
        return pd.DataFrame()
    print(f"Loaded {len(df)} {label} profiles from {path.name}")
    return df


def filter_by_minutes(df: pd.DataFrame, minimum: int, label: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["minutes"] = pd.to_numeric(df.get("minutes", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    eligible = df[df["minutes"] >= minimum].copy()
    excluded = len(df) - len(eligible)
    if excluded:
        print(f"  {label}: excluded {excluded} players below {minimum}-minute threshold")
    return eligible.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Feature utilities
# ---------------------------------------------------------------------------

def ordered_feature_cols(feature_groups: dict) -> list[str]:
    seen: set[str] = set()
    cols: list[str] = []
    for group_cols in feature_groups.values():
        for col in group_cols:
            if col not in seen and col not in IDENTITY_COLS:
                seen.add(col)
                cols.append(col)
    return cols


def numeric_features(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Return a float DataFrame with only the requested feature columns."""
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()
    for col in available:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    # Add missing columns as NaN
    for col in cols:
        if col not in out.columns:
            out[col] = np.nan
    return out[cols]


def zscore_within_group(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score each column; return 0 for constant columns."""
    result = df.copy()
    for col in df.columns:
        std = df[col].std(ddof=0)
        mean = df[col].mean()
        if std > 0:
            result[col] = (df[col] - mean) / std
        else:
            result[col] = 0.0
    return result.fillna(0.0)


def weighted_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray, weights: np.ndarray) -> float:
    """Weighted cosine similarity between two vectors."""
    wa = vec_a * weights
    wb = vec_b * weights
    norm_a = np.linalg.norm(wa)
    norm_b = np.linalg.norm(wb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(wa, wb) / (norm_a * norm_b))


def build_weight_vector(
    all_feature_cols: list[str],
    feature_groups: dict,
    position_weights: dict,
    position_group: str,
) -> np.ndarray:
    """Build a per-feature weight vector from group-level weights."""
    group_weight_map = position_weights.get(position_group, {})
    # Invert: col -> group
    col_to_group: dict[str, str] = {}
    for group, cols in feature_groups.items():
        for col in cols:
            col_to_group[col] = group

    weight_vec = np.zeros(len(all_feature_cols))
    for i, col in enumerate(all_feature_cols):
        group = col_to_group.get(col)
        if group:
            group_cols = feature_groups.get(group, [])
            group_weight = float(group_weight_map.get(group, 0.0))
            # Distribute group weight evenly across its features
            n = len(group_cols)
            weight_vec[i] = group_weight / n if n > 0 else 0.0
    return weight_vec


# ---------------------------------------------------------------------------
# Ideal profile
# ---------------------------------------------------------------------------

def build_ideal_profiles(
    internal: pd.DataFrame,
    position_groups: list[str],
    all_feature_cols: list[str],
) -> dict[str, pd.Series]:
    """Build mean feature profile per position group from eligible internal players."""
    profiles: dict[str, pd.Series] = {}
    if internal.empty:
        return profiles
    for pg in position_groups:
        group_df = internal[internal["position_group"].eq(pg)]
        if group_df.empty:
            continue
        feats = numeric_features(group_df, all_feature_cols)
        profiles[pg] = feats.mean()
    return profiles


def build_loo_ideal_profiles(
    internal: pd.DataFrame,
    position_groups: list[str],
    all_feature_cols: list[str],
) -> dict[str, dict]:
    """Build per-player leave-one-out ideal profiles.

    Returns a dict keyed by player_id, each value being the mean of all
    other eligible players in the same position group. Falls back to the
    full group mean when a group has only one player.
    """
    loo: dict[str, pd.Series] = {}
    if internal.empty:
        return loo
    for pg in position_groups:
        group_df = internal[internal["position_group"].eq(pg)].copy()
        if group_df.empty:
            continue
        full_feats = numeric_features(group_df, all_feature_cols)
        full_mean = full_feats.mean()
        for idx in group_df.index:
            pid = str(group_df.loc[idx, "player_id"])
            others = group_df.drop(index=idx)
            if others.empty:
                loo[pid] = full_mean
            else:
                loo[pid] = numeric_features(others, all_feature_cols).mean()
    return loo


def save_ideal_profiles(ideal_profiles: dict[str, pd.Series], output_dir: Path) -> None:
    if not ideal_profiles:
        return
    rows = []
    for pg, series in ideal_profiles.items():
        row = {"position_group": pg}
        row.update(series.to_dict())
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "position_ideal_profiles.csv", index=False)
    print(f"  Saved ideal profiles for: {list(ideal_profiles.keys())}")


# ---------------------------------------------------------------------------
# Similarity scoring
# ---------------------------------------------------------------------------

def score_against_ideal(
    candidates: pd.DataFrame,
    ideal_profiles: dict,
    position_groups: list[str],
    feature_groups: dict,
    position_weights: dict,
    all_feature_cols: list[str],
) -> pd.DataFrame:
    """Score each candidate against their position group ideal profile.

    ideal_profiles can be:
      - dict[pg_str -> pd.Series]         (normal mode: one ideal per group)
      - dict[player_id_str -> pd.Series]  (LOO mode: one ideal per player)

    The function detects the mode by checking whether any key matches a
    position group name.
    """
    if candidates.empty or not ideal_profiles:
        return pd.DataFrame()

    # Detect mode: if any key is a known position group, use group mode.
    pg_mode = any(k in position_groups for k in ideal_profiles)

    result_rows = []

    for pg in position_groups:
        if pg_mode and pg not in ideal_profiles:
            continue
        group_candidates = candidates[candidates["position_group"].eq(pg)].copy()
        if group_candidates.empty:
            continue

        weight_vec = build_weight_vector(all_feature_cols, feature_groups, position_weights, pg)

        feats_raw = numeric_features(group_candidates, all_feature_cols)
        stds = feats_raw.std(ddof=0).replace(0, 1)
        means = feats_raw.mean()

        def z_normalize(series: pd.Series) -> np.ndarray:
            return ((series.reindex(all_feature_cols).fillna(0.0) - means) / stds).fillna(0.0).values

        feats_z = ((feats_raw - means) / stds).fillna(0.0)

        for idx, row in group_candidates.iterrows():
            pid = str(row.get("player_id", ""))
            if pg_mode:
                ideal_series = ideal_profiles[pg]
            else:
                # LOO: use this player's specific ideal
                ideal_series = ideal_profiles.get(pid, pd.Series(dtype=float))

            ideal_z = z_normalize(ideal_series)
            candidate_vec = feats_z.loc[idx].values
            sim = weighted_cosine_similarity(candidate_vec, ideal_z, weight_vec)
            fit_score = round((sim + 1) / 2 * 100, 1)

            feat_row = feats_raw.loc[idx]
            data_completeness = int(feat_row.notna().sum())
            total_features = len(all_feature_cols)
            notes_raw = row.get("notes", "")
            notes = "" if (notes_raw is None or str(notes_raw).strip() in ("", "nan")) else str(notes_raw).strip()

            result_rows.append({
                "position_group": pg,
                "player_name": row.get("player_name", ""),
                "player_id": pid,
                "team": row.get("team", ""),
                "season": row.get("season", ""),
                "source_system": row.get("source_system", ""),
                "minutes": row.get("minutes", ""),
                "matches": row.get("matches", ""),
                "primary_position": row.get("primary_position", ""),
                "cosine_similarity": round(sim, 4),
                "fit_score": fit_score,
                "features_with_data": data_completeness,
                "total_features": total_features,
                "data_completeness_pct": round(data_completeness / total_features * 100, 1),
                "notes": notes,
            })

    if not result_rows:
        return pd.DataFrame()

    df = pd.DataFrame(result_rows)
    df = df.sort_values(["position_group", "fit_score"], ascending=[True, False]).reset_index(drop=True)
    df.insert(0, "rank_within_group", df.groupby("position_group").cumcount() + 1)
    return df


# ---------------------------------------------------------------------------
# Feature gaps
# ---------------------------------------------------------------------------

def compute_feature_gaps(
    candidates: pd.DataFrame,
    ideal_profiles: dict[str, pd.Series],
    position_groups: list[str],
    all_feature_cols: list[str],
) -> pd.DataFrame:
    """Compute per-feature delta vs ideal profile for each candidate."""
    if candidates.empty or not ideal_profiles:
        return pd.DataFrame()

    rows = []
    for pg in position_groups:
        if pg not in ideal_profiles:
            continue
        group_df = candidates[candidates["position_group"].eq(pg)].copy()
        if group_df.empty:
            continue
        ideal = ideal_profiles[pg].reindex(all_feature_cols).fillna(np.nan)
        feats = numeric_features(group_df, all_feature_cols)

        for idx, row in group_df.iterrows():
            feat_row = feats.loc[idx]
            for col in all_feature_cols:
                candidate_val = feat_row[col]
                ideal_val = ideal[col]
                if pd.isna(candidate_val) or pd.isna(ideal_val):
                    gap = np.nan
                    direction = "no_data"
                else:
                    gap = round(float(candidate_val) - float(ideal_val), 4)
                    direction = "above" if gap > 0 else ("below" if gap < 0 else "at_ideal")
                rows.append({
                    "position_group": pg,
                    "player_name": row.get("player_name", ""),
                    "player_id": row.get("player_id", ""),
                    "feature": col,
                    "candidate_value": round(float(candidate_val), 4) if not pd.isna(candidate_val) else np.nan,
                    "ideal_value": round(float(ideal_val), 4) if not pd.isna(ideal_val) else np.nan,
                    "gap": gap,
                    "direction": direction,
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Nearest CofC comps
# ---------------------------------------------------------------------------

def compute_internal_comps(
    candidates: pd.DataFrame,
    internal: pd.DataFrame,
    position_groups: list[str],
    feature_groups: dict,
    position_weights: dict,
    all_feature_cols: list[str],
    top_n: int,
    self_comp: bool,
) -> pd.DataFrame:
    """Find the top-N nearest internal CofC players for each candidate."""
    if candidates.empty or internal.empty:
        return pd.DataFrame()

    rows = []
    for pg in position_groups:
        group_candidates = candidates[candidates["position_group"].eq(pg)].copy()
        group_internal = internal[internal["position_group"].eq(pg)].copy()
        if group_candidates.empty or group_internal.empty:
            continue

        weight_vec = build_weight_vector(all_feature_cols, feature_groups, position_weights, pg)

        # Build combined pool for z-scoring so both sides use same scale
        combined = pd.concat([group_internal, group_candidates], ignore_index=True)
        combined_feats = numeric_features(combined, all_feature_cols)
        stds = combined_feats.std(ddof=0).replace(0, 1)
        means = combined_feats.mean()

        def normalize(df_subset: pd.DataFrame) -> np.ndarray:
            feats = numeric_features(df_subset, all_feature_cols)
            return ((feats - means) / stds).fillna(0.0).values

        internal_vecs = normalize(group_internal)
        candidate_vecs = normalize(group_candidates)

        for c_idx, (_, cand_row) in enumerate(group_candidates.iterrows()):
            cand_vec = candidate_vecs[c_idx]
            sims: list[tuple[float, str, str, float, float]] = []

            for i_idx, (_, int_row) in enumerate(group_internal.iterrows()):
                # Skip self-comp when running internal-only mode
                if not self_comp and int_row.get("player_id") == cand_row.get("player_id"):
                    continue
                int_vec = internal_vecs[i_idx]
                sim = weighted_cosine_similarity(cand_vec, int_vec, weight_vec)
                sims.append((
                    sim,
                    str(int_row.get("player_name", "")),
                    str(int_row.get("player_id", "")),
                    float(int_row.get("minutes", 0) or 0),
                    float(int_row.get("matches", 0) or 0),
                ))

            sims.sort(key=lambda x: x[0], reverse=True)
            for rank, (sim, comp_name, comp_id, comp_min, comp_matches) in enumerate(sims[:top_n], start=1):
                rows.append({
                    "position_group": pg,
                    "player_name": cand_row.get("player_name", ""),
                    "player_id": cand_row.get("player_id", ""),
                    "comp_rank": rank,
                    "comp_player_name": comp_name,
                    "comp_player_id": comp_id,
                    "comp_minutes": comp_min,
                    "comp_matches": comp_matches,
                    "cosine_similarity": round(sim, 4),
                    "fit_score": round((sim + 1) / 2 * 100, 1),
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Shortlist reports (Markdown)
# ---------------------------------------------------------------------------

def build_shortlist_reports(
    similarity_df: pd.DataFrame,
    gaps_df: pd.DataFrame,
    comps_df: pd.DataFrame,
    position_groups: list[str],
    output_dir: Path,
    season: str,
    top_n: int,
    internal_only: bool,
) -> None:
    if similarity_df.empty:
        return

    label = "Internal Roster" if internal_only else "Recruit"

    for pg in position_groups:
        pg_sim = similarity_df[similarity_df["position_group"].eq(pg)].head(top_n)
        if pg_sim.empty:
            continue

        lines: list[str] = [
            f"# {pg} {label} Similarity Shortlist",
            "",
            f"Season: {season}  |  Position group: `{pg}`  |  "
            f"Mode: {'internal-only validation' if internal_only else 'recruit evaluation'}",
            "",
        ]

        if internal_only:
            # In internal-only mode the ideal fit score is not meaningful
            # (each player IS the group mean). Lead with roster summary instead.
            lines += [
                "## Roster Summary",
                "",
                "| Player | Minutes | Matches | Data Completeness | Notes |",
                "| --- | --- | --- | --- | --- |",
            ]
            for _, row in pg_sim.iterrows():
                notes = str(row.get("notes", "")).strip() or "—"
                lines.append(
                    f"| {row['player_name']} "
                    f"| {row['minutes']} "
                    f"| {row['matches']} "
                    f"| {row['data_completeness_pct']}% "
                    f"| {notes} |"
                )
        else:
            lines += [
                "## Ranked by Fit Score",
                "",
                "| Rank | Player | Team | Minutes | Matches | Fit Score | Data Completeness | Notes |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
            for _, row in pg_sim.iterrows():
                notes = str(row.get("notes", "")).strip() or "—"
                lines.append(
                    f"| {row['rank_within_group']} "
                    f"| {row['player_name']} "
                    f"| {row['team']} "
                    f"| {row['minutes']} "
                    f"| {row['matches']} "
                    f"| {row['fit_score']} "
                    f"| {row['data_completeness_pct']}% "
                    f"| {notes} |"
                )

        lines += ["", "## Nearest CofC Comps", ""]

        if not comps_df.empty:
            pg_comps = comps_df[comps_df["position_group"].eq(pg)]
            if not pg_comps.empty:
                lines += [
                    "| Player | Comp Rank | CofC Comp | Comp Minutes | Fit Score |",
                    "| --- | --- | --- | --- | --- |",
                ]
                for _, row in pg_comps.iterrows():
                    lines.append(
                        f"| {row['player_name']} "
                        f"| {row['comp_rank']} "
                        f"| {row['comp_player_name']} "
                        f"| {row['comp_minutes']} "
                        f"| {row['fit_score']} |"
                    )
            else:
                lines.append("_No comps available for this position group._")
        else:
            lines.append("_No comps data._")

        lines += ["", "## Top Feature Gaps vs Ideal Profile", ""]

        if not gaps_df.empty:
            pg_gaps = gaps_df[
                gaps_df["position_group"].eq(pg) &
                gaps_df["gap"].notna()
            ].copy()
            if not pg_gaps.empty:
                # Show largest absolute gaps across all players in this group
                pg_gaps["abs_gap"] = pg_gaps["gap"].abs()
                top_gaps = (
                    pg_gaps.sort_values("abs_gap", ascending=False)
                    .head(20)
                )
                lines += [
                    "| Player | Feature | Candidate | Ideal | Gap | Direction |",
                    "| --- | --- | --- | --- | --- | --- |",
                ]
                for _, row in top_gaps.iterrows():
                    lines.append(
                        f"| {row['player_name']} "
                        f"| {row['feature']} "
                        f"| {row['candidate_value']} "
                        f"| {row['ideal_value']} "
                        f"| {row['gap']:+.4f} "
                        f"| {row['direction']} |"
                    )
            else:
                lines.append("_No gap data available._")
        else:
            lines.append("_No gap data._")

        lines += [
            "",
            "---",
            "",
            "_This report is generated from profile data and weighted cosine similarity. "
            "Fit score reflects statistical similarity to the CofC position group ideal profile — "
            "not an absolute quality rating. Minutes below threshold and missing features reduce reliability._",
            "",
        ]

        slug = pg.lower().replace("_", "-")
        mode_suffix = "_internal" if internal_only else ""
        out_path = output_dir / f"shortlist_{slug}{mode_suffix}.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Wrote shortlist: {out_path.name}")


if __name__ == "__main__":
    main()
