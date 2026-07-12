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

    target = df[df["is_target_team"]].copy().reset_index(drop=True)
    opponents = df[~df["is_target_team"]].copy().reset_index(drop=True)

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

    return merged.sort_values("date").reset_index(drop=True)


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
