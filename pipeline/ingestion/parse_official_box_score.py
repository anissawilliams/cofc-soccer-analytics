"""Extract official CofC minutes and starter status from a SIDEARM box score PDF."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from parse_wyscout import normalize_player_name


OFFICIAL_MARKER = "Official Soccer Box Score - Final"
TEAM_NAMES = ("Col. of Charleston", "Charleston Cougars", "College of Charleston")
PLAYER_ROW = re.compile(
    r"^\s*(?:(gk|def|mid|fwd)\s+)?(\d+)\s+(.+?)\s+"
    r"(?:-|\d+)\s+(?:-|\d+)\s+(?:-|\d+)\s+(?:-|\d+)\s+(?:-|\d+)\s+(\d+)\s*$",
    re.IGNORECASE,
)


def _identity_matches(short_name: str, full_name: str) -> bool:
    """Match a Wyscout-style roster name (M. Lenert) to a full box-score name."""
    short_tokens = re.findall(r"[a-z]+", normalize_player_name(short_name))
    full_tokens = re.findall(r"[a-z]+", normalize_player_name(full_name))
    if not short_tokens or not full_tokens:
        return False
    if short_tokens[-1] != full_tokens[-1]:
        return False
    return short_tokens[0][0] == full_tokens[0][0]


def parse_official_minutes_text(text: str, roster_path: Path, source_name: str) -> list[dict]:
    """Parse the CofC roster column from layout-preserving official-box-score text."""
    if OFFICIAL_MARKER not in text:
        raise ValueError("PDF is not an official final soccer box score")

    lines = text.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if len(list(re.finditer(r"\bPos\b", line))) == 2 and line.count("Player") >= 2
        ),
        None,
    )
    if header_index is None:
        raise ValueError("Could not find the two-team player table")

    header = lines[header_index]
    column_starts = [match.start() for match in re.finditer(r"\bPos\b", header)]
    boundary = column_starts[1]
    team_line = next(
        (
            line
            for line in reversed(lines[:header_index])
            if any(team_name in line for team_name in TEAM_NAMES)
        ),
        "",
    )
    team_position = min(
        (team_line.find(name) for name in TEAM_NAMES if name in team_line),
        default=-1,
    )
    if team_position < 0:
        raise ValueError("Could not locate College of Charleston in the player table")
    use_right_column = team_position >= boundary

    roster: dict[str, list[str]] = {}
    with roster_path.open(newline="", encoding="utf-8-sig") as handle:
        for roster_row in csv.DictReader(handle):
            jersey = str(roster_row.get("number") or "").strip()
            name = str(roster_row.get("name") or "").strip()
            if jersey and name:
                roster.setdefault(jersey, []).append(name)
    rows: list[dict] = []
    substitutes = False
    for line in lines[header_index + 1 :]:
        if "##" in line and "Goalkeepers" in line:
            break
        segment = line[boundary:] if use_right_column else line[:boundary]
        if "-- Substitutes --" in segment:
            substitutes = True
            continue
        if "Totals" in segment:
            continue
        match = PLAYER_ROW.match(segment)
        if not match:
            continue
        position, jersey, player_name, minutes = match.groups()
        valid_names = roster.get(jersey, [])
        roster_name = next(
            (name for name in valid_names if _identity_matches(name, player_name)),
            None,
        )
        if roster_name is None:
            raise ValueError(
                f"Official box score player does not match roster: #{jersey} {player_name}"
            )
        rows.append({
            "player_name": roster_name,
            "official_name": player_name.strip(),
            "jersey": jersey,
            "estimated_minutes": int(minutes),
            "started": not substitutes,
            "position": (position or "").lower(),
            "source_file": source_name,
        })

    if len(rows) < 11:
        raise ValueError(f"Only {len(rows)} CofC player rows were found; expected at least 11")
    jerseys = [row["jersey"] for row in rows]
    if len(jerseys) != len(set(jerseys)):
        raise ValueError("Official box score contains duplicate CofC jersey numbers")
    if sum(bool(row["started"]) for row in rows) != 11:
        raise ValueError("Official box score did not identify exactly 11 CofC starters")
    return rows


def extract_official_minutes(pdf_path: Path, roster_path: Path) -> list[dict]:
    """Read one official PDF. Import pypdf lazily so XML-only intake still works."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to read the official box score PDF") from exc

    reader = PdfReader(str(pdf_path))
    text = "\n".join(
        page.extract_text(extraction_mode="layout") or "" for page in reader.pages[:2]
    )
    return parse_official_minutes_text(text, roster_path, pdf_path.name)


def discover_official_minutes(input_dir: Path, roster_path: Path) -> tuple[dict, list[dict]]:
    """Find one unique official box score and return a fail-closed readiness result."""
    pdfs = sorted(set(input_dir.rglob("*.pdf")) | set(input_dir.rglob("*.PDF")))
    parsed: list[tuple[Path, list[dict]]] = []
    errors: list[str] = []
    for pdf_path in pdfs:
        try:
            rows = extract_official_minutes(pdf_path, roster_path)
        except ValueError as exc:
            if "not an official final" not in str(exc):
                errors.append(f"{pdf_path.name}: {exc}")
            continue
        except RuntimeError as exc:
            return {"ready": False, "reason": str(exc)}, []
        except Exception as exc:
            errors.append(f"{pdf_path.name}: could not read PDF ({type(exc).__name__}: {exc})")
            continue
        parsed.append((pdf_path, rows))

    if errors:
        return {"ready": False, "reason": "; ".join(errors)}, []
    if not parsed:
        return {
            "ready": False,
            "reason": "add the official final box score PDF for exact minutes and starters",
        }, []

    signatures = {
        tuple((row["jersey"], row["estimated_minutes"], row["started"]) for row in rows)
        for _, rows in parsed
    }
    if len(signatures) != 1:
        return {
            "ready": False,
            "reason": "multiple official box score PDFs disagree; keep one current version",
        }, []
    selected_path, rows = parsed[0]
    return {
        "ready": True,
        "reason": "official minutes and starters parsed successfully",
        "selected_file": selected_path.name,
        "players": len(rows),
        "starters": sum(bool(row["started"]) for row in rows),
    }, rows
