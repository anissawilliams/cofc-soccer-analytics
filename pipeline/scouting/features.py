from __future__ import annotations

from pathlib import Path

import pandas as pd


MATCH_COLUMNS = [
    "date",
    "match",
    "competition",
    "duration",
    "team",
    "scheme",
    "goals",
    "xg",
    "shots",
    "shots_on_target",
    "shot_conversion_pct",
    "passes",
    "passes_accurate",
    "pass_accuracy_pct",
    "possession_pct",
    "losses",
    "losses_low",
    "losses_mid",
    "losses_high",
    "recoveries",
    "recoveries_low",
    "recoveries_mid",
    "recoveries_high",
    "duels",
    "duels_won",
    "duel_win_pct",
]

ROLLING_WINDOWS = (3, 5)
ROLLING_BASE_COLUMNS = [
    "points",
    "goals",
    "goals_against",
    "xg",
    "xg_against",
    "shots",
    "shots_on_target",
    "shots_on_target_against",
    "possession_pct",
    "recoveries",
]


def load_wyscout_match_stats(path: str | Path, team_name: str) -> pd.DataFrame:
    """Load Wyscout team match stats exported to the current season workbook shape."""

    df = pd.read_excel(path, header=None, skiprows=3)
    df.columns = MATCH_COLUMNS
    df = df[df["date"].notna()].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["is_target_team"] = df["team"].astype(str).eq(team_name)
    df["result"] = df.apply(_parse_result_from_match_name, axis=1)
    return df


def build_match_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build one row per match from the target team's point of view."""

    enriched = add_rolling_momentum_features(df)
    rolling_columns = [col for col in enriched.columns if col.startswith("rolling_")]

    target = enriched[enriched["is_target_team"]].copy().reset_index(drop=True)
    opponents = enriched[~enriched["is_target_team"]].copy().reset_index(drop=True)

    merged = target.merge(
        opponents[
            [
                "match",
                "date",
                "team",
                "goals",
                "xg",
                "shots",
                "shots_on_target",
                "pass_accuracy_pct",
                "possession_pct",
                "recoveries",
                "duels_won",
            ]
            + rolling_columns
        ],
        on=["match", "date"],
        suffixes=("_cofc", "_opp"),
    )

    merged = merged.rename(columns={"team_opp": "opponent"})
    merged["xg_diff"] = merged["xg_cofc"] - merged["xg_opp"]
    merged["possession_diff"] = (
        merged["possession_pct_cofc"] - merged["possession_pct_opp"]
    )
    merged["shot_diff"] = merged["shots_cofc"] - merged["shots_opp"]
    merged["pass_acc_diff"] = (
        merged["pass_accuracy_pct_cofc"] - merged["pass_accuracy_pct_opp"]
    )
    merged["recovery_diff"] = merged["recoveries_cofc"] - merged["recoveries_opp"]
    for col in rolling_columns:
        cofc_col = f"{col}_cofc"
        opp_col = f"{col}_opp"
        if cofc_col in merged.columns and opp_col in merged.columns:
            merged[f"{col}_diff"] = merged[cofc_col] - merged[opp_col]

    return merged.sort_values("date").reset_index(drop=True)


def add_rolling_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add pre-match rolling features for each team without leaking current-match data."""
    enriched = _add_opponent_context(df)
    rows = []
    for _, group in enriched.sort_values("date").groupby("team", sort=False):
        group = group.copy().sort_values("date")
        for window in ROLLING_WINDOWS:
            shifted = group[ROLLING_BASE_COLUMNS].shift(1)
            rolling = shifted.rolling(window=window, min_periods=1).mean()
            for col in ROLLING_BASE_COLUMNS:
                group[f"rolling_{col}_last{window}"] = rolling[col]
        group["rolling_weighted_form_last5"] = _weighted_recent_form(group["points"], window=5)
        group["rolling_prior_matches"] = group.groupby("team").cumcount()
        rows.append(group.dropna(axis=1, how="all"))
    if not rows:
        return enriched

    out = pd.concat(rows).sort_values(["date", "match", "team"]).reset_index(drop=True)
    for window in ROLLING_WINDOWS:
        if _has_columns(out, [f"rolling_goals_last{window}", f"rolling_goals_against_last{window}"]):
            out[f"rolling_goal_diff_last{window}"] = (
                out[f"rolling_goals_last{window}"] - out[f"rolling_goals_against_last{window}"]
            )
        if _has_columns(out, [f"rolling_xg_last{window}", f"rolling_xg_against_last{window}"]):
            out[f"rolling_xg_diff_last{window}"] = (
                out[f"rolling_xg_last{window}"] - out[f"rolling_xg_against_last{window}"]
            )
        if _has_columns(out, [f"rolling_shots_on_target_last{window}", f"rolling_shots_on_target_against_last{window}"]):
            out[f"rolling_sot_diff_last{window}"] = (
                out[f"rolling_shots_on_target_last{window}"]
                - out[f"rolling_shots_on_target_against_last{window}"]
            )
    return out


def _has_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    return all(column in df.columns for column in columns)


def _add_opponent_context(df: pd.DataFrame) -> pd.DataFrame:
    """Attach opponent goals/xG/SOT for team-level rolling calculations."""
    base = df.copy()
    opponent = base[
        [
            "match",
            "date",
            "team",
            "goals",
            "xg",
            "shots_on_target",
        ]
    ].rename(
        columns={
            "team": "opponent_team",
            "goals": "goals_against",
            "xg": "xg_against",
            "shots_on_target": "shots_on_target_against",
        }
    )
    merged = base.merge(opponent, on=["match", "date"])
    merged = merged[merged["team"].ne(merged["opponent_team"])].copy()
    merged["points"] = merged["result"].map({"W": 3, "D": 1, "L": 0})
    return merged


def _weighted_recent_form(points: pd.Series, window: int) -> pd.Series:
    """Return a 0-1 weighted points form where recent matches matter more."""
    values = points.shift(1).reset_index(drop=True)
    output: list[float | None] = []
    for idx in range(len(values)):
        start = max(0, idx - window + 1)
        sample = values.iloc[start : idx + 1].dropna()
        if sample.empty:
            output.append(None)
            continue
        weights = pd.Series(range(1, len(sample) + 1), index=sample.index, dtype=float)
        max_points = 3.0 * weights.sum()
        output.append(float((sample * weights).sum() / max_points))
    return pd.Series(output, index=points.index)


def feature_matrix(
    features: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    missing = [column for column in feature_columns if column not in features.columns]
    if missing:
        raise KeyError(f"Missing model feature columns: {missing}")

    X = features[feature_columns].apply(pd.to_numeric, errors="coerce")
    y = features["result"].copy()
    keep = X.notna().all(axis=1) & y.notna()
    return X.loc[keep].reset_index(drop=True), y.loc[keep].reset_index(drop=True)


def _parse_result_from_match_name(row: pd.Series) -> str | None:
    match_str = str(row["match"])
    team = str(row["team"])

    try:
        score_part = match_str.split(" ")[-1]
        home_team = match_str.split(" - ")[0].strip()
        home_goals_raw, away_goals_raw = score_part.split(":")
        home_goals = int(home_goals_raw)
        away_goals = int(away_goals_raw)
    except (IndexError, ValueError):
        return None

    is_home = home_team == team
    team_goals = home_goals if is_home else away_goals
    opponent_goals = away_goals if is_home else home_goals

    if team_goals > opponent_goals:
        return "W"
    if team_goals < opponent_goals:
        return "L"
    return "D"
