from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from pipeline.scouting.features import (
    MATCH_COLUMNS,
    add_rolling_momentum_features,
    load_wyscout_match_stats,
)


TREND_COLUMNS = [
    "points",
    "goals",
    "goals_against",
    "xg",
    "xg_against",
    "shots",
    "shots_on_target",
    "shots_on_target_against",
    "possession_pct",
    "pass_accuracy_pct",
    "recoveries",
    "duels_won",
]


def load_opponent_history(
    paths: Iterable[str | Path],
    opponent_name: str,
    cutoff_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Load and reconcile Wyscout team-stat exports for one opponent.

    Excel files use the native Wyscout season workbook shape. CSV files may
    contain either the same 26 columns or named columns matching MATCH_COLUMNS.
    Only matches strictly before cutoff_date are retained, preventing a report
    from seeing the match it is intended to scout or any later result.
    """

    frames: list[pd.DataFrame] = []
    for raw_path in paths:
        path = Path(raw_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            frame = _load_match_report_pdf(path, opponent_name)
        elif suffix in {".xlsx", ".xls"}:
            frame = load_wyscout_match_stats(path, opponent_name)
        elif suffix == ".csv":
            frame = _load_csv(path, opponent_name)
        else:
            continue
        frame["source_file"] = path.name
        frames.append(frame)

    if not frames:
        raise ValueError(
            "No Wyscout Match Report PDFs or .xlsx, .xls, or .csv team-stat files were found."
        )

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined[combined["date"].notna()].copy()
    if cutoff_date is not None:
        cutoff = pd.Timestamp(cutoff_date).normalize()
        combined = combined[combined["date"].dt.normalize() < cutoff].copy()

    combined = combined.drop_duplicates(
        subset=["date", "match", "team"], keep="last"
    ).sort_values(["date", "match", "team"])
    _validate_history(combined, opponent_name)
    return combined.reset_index(drop=True)


def build_opponent_trends(history: pd.DataFrame, opponent_name: str) -> pd.DataFrame:
    """Return one chronological row per opponent match with pre-match rollups."""

    enriched = add_rolling_momentum_features(history)
    target = enriched[enriched["team"].astype(str).eq(opponent_name)].copy()
    if target.empty:
        raise ValueError(f"No rows found for opponent {opponent_name!r}.")

    columns = [
        "date",
        "match",
        "competition",
        "team",
        "opponent_team",
        "result",
        *TREND_COLUMNS,
    ]
    columns.extend(column for column in target.columns if column.startswith("rolling_"))
    columns.extend(["source_file"] if "source_file" in target.columns else [])
    return target[[column for column in columns if column in target.columns]].sort_values(
        "date"
    ).reset_index(drop=True)


def summarize_recent_form(trends: pd.DataFrame, window: int = 5) -> dict:
    """Build a compact, JSON-safe recent-form summary for notebook reporting."""

    if trends.empty:
        raise ValueError("Cannot summarize an empty opponent history.")
    recent = trends.tail(window)
    numeric = [column for column in TREND_COLUMNS if column in recent.columns]
    averages = recent[numeric].apply(pd.to_numeric, errors="coerce").mean()
    return {
        "matches_available": int(len(trends)),
        "matches_in_window": int(len(recent)),
        "date_from": recent["date"].min().date().isoformat(),
        "date_to": recent["date"].max().date().isoformat(),
        "record": {
            label: int((recent["result"] == label).sum()) for label in ("W", "D", "L")
        },
        "averages": {
            column: round(float(value), 3)
            for column, value in averages.items()
            if pd.notna(value)
        },
    }


def _load_csv(path: Path, opponent_name: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if not set(MATCH_COLUMNS).issubset(frame.columns):
        if frame.shape[1] != len(MATCH_COLUMNS):
            raise ValueError(
                f"{path.name} is not a supported Wyscout team-stat CSV: "
                f"expected named columns or {len(MATCH_COLUMNS)} columns."
            )
        frame.columns = MATCH_COLUMNS
    frame = frame[frame["date"].notna()].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["is_target_team"] = frame["team"].astype(str).eq(opponent_name)
    frame["result"] = frame.apply(_result_from_goals, axis=1)
    return frame


def _load_match_report_pdf(path: Path, opponent_name: str) -> pd.DataFrame:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment-specific dependency
        raise RuntimeError("Install pypdf>=5.0.0 to read Wyscout Match Report PDFs.") from exc

    reader = PdfReader(path)
    page_texts = [page.extract_text() or "" for page in reader.pages]
    if not page_texts:
        raise ValueError(f"{path.name} has no readable pages.")
    stats_text = next(
        (
            text
            for text in page_texts
            if "Recoveries / low / medium / high" in text
            and "Total passes / accurate" in text
            and "Possession %" in text
        ),
        None,
    )
    if stats_text is None:
        raise ValueError(
            f"{path.name} is not a supported full Wyscout Match Report: "
            "the Team Stats page was not found."
        )
    return _parse_match_report_text(page_texts[0], stats_text, opponent_name)


def _parse_match_report_text(
    cover_text: str, stats_text: str, opponent_name: str
) -> pd.DataFrame:
    lines = [line.strip() for line in cover_text.splitlines() if line.strip()]
    score_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(r"\d+\s*[–—-]\s*\d+", line)
        ),
        None,
    )
    if score_index is None or score_index < 2:
        raise ValueError("Could not read the two teams and final score from the PDF cover.")
    home_team, away_team = lines[score_index - 2 : score_index]
    home_goals, away_goals = (
        int(value) for value in re.split(r"\s*[–—-]\s*", lines[score_index])
    )
    date_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", cover_text)
    if date_match is None:
        raise ValueError("Could not read the match date from the PDF cover.")
    match_date = pd.to_datetime(date_match.group(1), dayfirst=True)
    date_line = next(line for line in lines if date_match.group(1) in line)
    competition = date_line.replace(date_match.group(1), "", 1).strip()
    competition = re.sub(r"\s+Round\s+\d+\s*$", "", competition, flags=re.IGNORECASE)

    pairs = {
        "xg": _number_pair(stats_text, "xG"),
        "shots_on_target_pair": _fraction_pair(stats_text, "Shots / on target"),
        "possession_pct": _number_pair(stats_text, "Possession %"),
        "passes_pair": _fraction_pair(stats_text, "Total passes / accurate"),
        "recoveries_parts": _slash_number_pair(
            stats_text, "Recoveries / low / medium / high", 4
        ),
        "losses_parts": _slash_number_pair(stats_text, "Losses / low / medium / high", 4),
        "duels_pair": _fraction_pair(stats_text, "Total duels / won"),
    }

    rows = []
    for side, (team, goals) in enumerate(
        ((home_team, home_goals), (away_team, away_goals))
    ):
        values = {column: None for column in MATCH_COLUMNS}
        shots, shots_on_target = pairs["shots_on_target_pair"][side]
        passes, passes_accurate = pairs["passes_pair"][side]
        duels, duels_won = pairs["duels_pair"][side]
        recoveries = pairs["recoveries_parts"][side]
        losses = pairs["losses_parts"][side]
        values.update(
            date=match_date,
            match=f"{home_team} - {away_team} {home_goals}:{away_goals}",
            competition=competition,
            duration=90,
            team=team,
            goals=goals,
            xg=pairs["xg"][side],
            shots=shots,
            shots_on_target=shots_on_target,
            passes=passes,
            passes_accurate=passes_accurate,
            pass_accuracy_pct=round(passes_accurate / passes * 100, 1) if passes else None,
            possession_pct=pairs["possession_pct"][side],
            losses=losses[0],
            losses_low=losses[1],
            losses_mid=losses[2],
            losses_high=losses[3],
            recoveries=recoveries[0],
            recoveries_low=recoveries[1],
            recoveries_mid=recoveries[2],
            recoveries_high=recoveries[3],
            duels=duels,
            duels_won=duels_won,
            duel_win_pct=round(duels_won / duels * 100, 1) if duels else None,
        )
        rows.append(values)

    frame = pd.DataFrame(rows)
    frame["is_target_team"] = frame["team"].astype(str).eq(opponent_name)
    frame["result"] = frame.apply(_result_from_goals, axis=1)
    return frame


def _number_pair(text: str, label: str) -> tuple[float, float]:
    match = re.search(
        rf"(?m)^{re.escape(label)}\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*$",
        text,
    )
    if match is None:
        raise ValueError(f"Could not extract {label!r} from the Wyscout Team Stats page.")
    return float(match.group(1)), float(match.group(2))


def _fraction_pair(text: str, label: str) -> tuple[tuple[int, int], tuple[int, int]]:
    match = re.search(
        rf"(?m)^{re.escape(label)}\s+(\d+)/(\d+)(?:\s+\d+%)?\s+"
        rf"(\d+)/(\d+)(?:\s+\d+%)?\s*$",
        text,
    )
    if match is None:
        raise ValueError(f"Could not extract {label!r} from the Wyscout Team Stats page.")
    return (int(match.group(1)), int(match.group(2))), (
        int(match.group(3)),
        int(match.group(4)),
    )


def _slash_number_pair(
    text: str, label: str, count: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    token = r"\d+" + r"/\d+" * (count - 1)
    match = re.search(
        rf"(?m)^{re.escape(label)}\s+({token})\s+({token})\s*$", text
    )
    if match is None:
        raise ValueError(f"Could not extract {label!r} from the Wyscout Team Stats page.")
    return tuple(int(value) for value in match.group(1).split("/")), tuple(
        int(value) for value in match.group(2).split("/")
    )


def _result_from_goals(row: pd.Series) -> str | None:
    try:
        team_goals = float(row["goals"])
    except (TypeError, ValueError):
        return None
    # The opposing row is attached later; native Wyscout match strings remain
    # the authoritative fallback for Excel imports.
    match = str(row.get("match", ""))
    try:
        home, score = match.rsplit(" ", 1)
        home_name = home.split(" - ", 1)[0].strip()
        home_goals, away_goals = (int(value) for value in score.split(":"))
        opponent_goals = away_goals if str(row["team"]) == home_name else home_goals
    except (ValueError, IndexError):
        return None
    if team_goals > opponent_goals:
        return "W"
    if team_goals < opponent_goals:
        return "L"
    return "D"


def _validate_history(history: pd.DataFrame, opponent_name: str) -> None:
    if history.empty:
        raise ValueError("No matches remain before the scouting cutoff date.")
    if not history["team"].astype(str).eq(opponent_name).any():
        choices = sorted(history["team"].dropna().astype(str).unique())
        raise ValueError(
            f"Opponent {opponent_name!r} was not found. Available team names: {choices}"
        )
    counts = history.groupby(["date", "match"])["team"].nunique()
    incomplete = counts[counts != 2]
    if not incomplete.empty:
        examples = [str(match) for _, match in incomplete.index[:3]]
        raise ValueError(
            "Each Wyscout match must contain exactly two team rows. "
            f"Incomplete or ambiguous matches: {examples}"
        )
