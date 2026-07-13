#!/usr/bin/env python3
"""
reconcile_coug_scores.py
========================
Build an explainable COUG score trace from athlete_event and compare it to
older PDF/CSV-derived COUG score files.

This does not decide which calculation is right. It creates the audit trail
needed to answer: "Why did the pipeline calculate a different PEAK/ASET value
than the coaches or the old match-report workflow?"

Examples:
    python pipeline/analytics/reconcile_coug_scores.py --season 2025 --slug 2025-11-02_uncw
    python pipeline/analytics/reconcile_coug_scores.py --season 2025 --all
    python pipeline/analytics/reconcile_coug_scores.py --season 2025 --slug 2025-11-02_uncw --dry-run
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Allow running as a plain script from the repo root.
INGESTION_DIR = Path(__file__).resolve().parents[1] / "ingestion"
if str(INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(INGESTION_DIR))

from source_paths import get_source_paths

PAGE_SIZE = 1000
CANDIDATE_PEAK_MODEL = "wyscout_peak_normalization_v1"
ADVANCE_ACTIONS_PER_CREDIT = 10
ADVANCE_CREDIT_WEIGHT = 0.5


@dataclass(frozen=True)
class ScoreFiles:
    legacy_csv: Path | None
    pdf_csv: Path | None


def normalize_name(name: str) -> str:
    name = str(name or "").strip().lower()
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return " ".join(name.split())


def slug_date(slug: str) -> str:
    return slug[:10]


def slug_opponent(slug: str) -> str:
    return slug.split("_", 1)[1] if "_" in slug else slug


def pretty_opponent(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug_opponent(slug).split("_"))


def fetch_all(client, table_name: str) -> pd.DataFrame:
    rows = []
    start = 0
    while True:
        resp = client.table(table_name).select("*").range(start, start + PAGE_SIZE - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return pd.DataFrame(rows)


def fetch_optional(client, table_name: str) -> pd.DataFrame:
    try:
        return fetch_all(client, table_name)
    except Exception as exc:
        print(f"Warning: could not fetch optional table '{table_name}': {exc}")
        return pd.DataFrame()


def get_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit(
            "Missing Python package 'supabase'. Install project dependencies with "
            "`pip install -r requirements.txt` before running reconciliation."
        ) from exc

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def latest_weights(weights: pd.DataFrame, version: str) -> pd.DataFrame:
    if weights.empty:
        return weights
    df = weights[weights["version"].astype(str) == str(version)].copy()
    if df.empty:
        raise ValueError(f"No metric_weight rows found for version '{version}'")
    df["effective_from_sort"] = pd.to_datetime(df.get("effective_from"), errors="coerce")
    df = df.sort_values(["metric_id", "effective_from_sort", "created_at"], na_position="first")
    return df.drop_duplicates(subset=["metric_id"], keep="last").drop(columns=["effective_from_sort"])


def score_bucket(category_code: str, metric_name: str) -> str:
    code = str(category_code or "").upper()
    name = str(metric_name or "").lower()
    if code.startswith("ASET"):
        return "aset"
    if code.startswith("PEAK"):
        return "peak"
    if code == "SET_PIECE":
        return "set_piece"
    if code == "POSITIONAL":
        return "positional"
    if code == "LOAD":
        return "load"
    if code == "TEAM":
        if "clean" in name or "concede" in name:
            return "aset"
        if "goal" in name:
            return "peak"
    return "other"


def normalize_metric_name(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def parse_context_labels(raw_context: object) -> set[str]:
    if pd.isna(raw_context):
        return set()
    if isinstance(raw_context, dict):
        context = raw_context
    else:
        try:
            context = ast.literal_eval(str(raw_context))
        except (ValueError, SyntaxError):
            return set()
    labels = set()
    for value in context.get("all_labels", []) or []:
        labels.add(normalize_metric_name(value))
    if context.get("wyscout_label"):
        labels.add(normalize_metric_name(context["wyscout_label"]))
    return labels


def load_peak_normalization() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "config" / "wyscout_peak_normalization.csv"
    if not path.exists():
        return pd.DataFrame(columns=[
            "raw_label_key", "normalized_metric", "peak_phase", "score_policy",
            "event_weight", "threshold_count", "threshold_score", "requires_success",
            "success_rule", "double_count_priority", "pass_threshold_rule",
            "official_status", "implementation_status", "notes",
        ])
    df = pd.read_csv(path)
    df["raw_label_key"] = df["raw_label_key"].fillna(df["raw_label"]).map(normalize_metric_name)
    df["normalized_metric"] = df["normalized_metric"].fillna("")
    df["peak_phase"] = df["peak_phase"].fillna("")
    df["score_policy"] = df["score_policy"].fillna("exclude")
    df["event_weight"] = pd.to_numeric(df["event_weight"], errors="coerce").fillna(0.0)
    df["threshold_count"] = pd.to_numeric(df["threshold_count"], errors="coerce")
    df["threshold_score"] = pd.to_numeric(df["threshold_score"], errors="coerce")
    df["requires_success"] = df["requires_success"].fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})
    for col in ["success_rule", "pass_threshold_rule", "official_status", "implementation_status", "notes"]:
        df[col] = df[col].fillna("")
    df["double_count_priority"] = pd.to_numeric(df["double_count_priority"], errors="coerce").fillna(99).astype(int)
    return df


def candidate_peak_event(row: pd.Series, peak_rules_by_key: dict[str, pd.Series]) -> pd.Series:
    labels = parse_context_labels(row.get("raw_value_context"))
    raw_key = normalize_metric_name(row.get("raw_metric_name"))

    rule_key = raw_key if raw_key in peak_rules_by_key else ""
    if raw_key == "shots" and "opportunity" in labels and "shots" in peak_rules_by_key:
        # Raw shot rows are too broad. Only treat them as PEAK when the parsed
        # context also says this shot was an Opportunity.
        rule_key = "shots"
    elif raw_key == "shots":
        rule_key = ""

    if not rule_key:
        return pd.Series({
            "candidate_peak_metric": "",
            "candidate_peak_phase": "",
            "candidate_peak_weight": 0.0,
            "candidate_peak_score": 0.0,
            "candidate_advance_action": 0,
            "candidate_advance_threshold_count": ADVANCE_ACTIONS_PER_CREDIT,
            "candidate_advance_threshold_score": ADVANCE_CREDIT_WEIGHT,
            "candidate_peak_model": CANDIDATE_PEAK_MODEL,
            "candidate_peak_note": "",
            "peak_score_policy": "",
            "peak_requires_success": False,
            "peak_success_rule": "",
            "peak_double_count_priority": 99,
            "peak_pass_threshold_rule": "",
            "peak_official_status": "",
            "peak_implementation_status": "",
        })

    rule = peak_rules_by_key[rule_key]
    score_policy = str(rule.get("score_policy", "exclude"))
    candidate_advance_action = int(score_policy == "threshold_count")
    threshold_count = pd.to_numeric(rule.get("threshold_count"), errors="coerce")
    threshold_score = pd.to_numeric(rule.get("threshold_score"), errors="coerce")
    if pd.isna(threshold_count):
        threshold_count = ADVANCE_ACTIONS_PER_CREDIT
    if pd.isna(threshold_score):
        threshold_score = ADVANCE_CREDIT_WEIGHT

    if score_policy == "exclude":
        event_score = 0.0
    elif score_policy == "threshold_count":
        event_score = 0.0
    elif score_policy in {"per_event", "contextual_event"}:
        raw_value = pd.to_numeric(row.get("raw_value"), errors="coerce")
        if pd.isna(raw_value):
            raw_value = 1.0
        event_score = float(raw_value) * float(rule.get("event_weight", 0.0))
    else:
        event_score = 0.0

    metric = str(rule.get("normalized_metric", ""))
    phase = str(rule.get("peak_phase", ""))
    weight = float(rule.get("event_weight", 0.0)) if score_policy != "threshold_count" else 0.0
    note = str(rule.get("notes", ""))
    if score_policy == "threshold_count":
        note = (
            f"Advance threshold action; score applied as {threshold_score:g} per "
            f"{int(threshold_count)} actions at player-match level"
        )

    return pd.Series({
        "candidate_peak_metric": metric,
        "candidate_peak_phase": phase,
        "candidate_peak_weight": weight,
        "candidate_peak_score": event_score,
        "candidate_advance_action": candidate_advance_action,
        "candidate_advance_threshold_count": float(threshold_count),
        "candidate_advance_threshold_score": float(threshold_score),
        "candidate_peak_model": CANDIDATE_PEAK_MODEL,
        "candidate_peak_note": note,
        "peak_score_policy": score_policy,
        "peak_requires_success": bool(rule.get("requires_success", False)),
        "peak_success_rule": str(rule.get("success_rule", "")),
        "peak_double_count_priority": int(rule.get("double_count_priority", 99)),
        "peak_pass_threshold_rule": str(rule.get("pass_threshold_rule", "")),
        "peak_official_status": str(rule.get("official_status", "")),
        "peak_implementation_status": str(rule.get("implementation_status", "")),
    })


def load_wyscout_metric_map() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "config" / "wyscout_coug_metric_map.csv"
    if not path.exists():
        return pd.DataFrame(columns=[
            "raw_metric_key", "mapped_metric_name", "mapped_score_bucket",
            "mapping_status", "default_include", "notes",
        ])
    df = pd.read_csv(path)
    df["raw_metric_key"] = df["raw_metric_name"].map(normalize_metric_name)
    df["mapped_metric_name"] = df["mapped_metric_name"].fillna("")
    df["mapped_score_bucket"] = df["mapped_score_bucket"].fillna("")
    df["mapping_status"] = df["mapping_status"].fillna("unmapped")
    df["mapping_notes"] = df["notes"].fillna("")
    return df[[
        "raw_metric_key", "mapped_metric_name", "mapped_score_bucket",
        "mapping_status", "default_include", "mapping_notes",
    ]]


def build_score_explainer(trace: pd.DataFrame) -> pd.DataFrame:
    if trace.empty:
        return pd.DataFrame()
    group_cols = [
        "session_id", "session_date", "season", "player", "player_key",
        "score_bucket", "raw_metric_name", "scoring_metric_name", "weight",
        "mapping_status", "mapping_notes", "calculation_note",
    ]
    available = [c for c in group_cols if c in trace.columns]
    grouped = (
        trace.groupby(available, dropna=False)
        .agg(
            event_count=("event_score", "size"),
            raw_value_total=("raw_value", "sum"),
            score_total=("event_score", "sum"),
            candidate_peak_total=("candidate_peak_score", "sum"),
            first_event_time=("event_time", "min"),
            last_event_time=("event_time", "max"),
        )
        .reset_index()
        .sort_values(["session_date", "player", "score_bucket", "score_total"], ascending=[True, True, True, False])
    )
    grouped["formula"] = (
        grouped["raw_value_total"].round(3).astype(str)
        + " x "
        + grouped["weight"].round(3).astype(str)
        + " = "
        + grouped["score_total"].round(3).astype(str)
    )
    grouped["candidate_peak_formula"] = grouped.apply(
        lambda row: (
            f"{round(row['candidate_peak_total'], 3)} candidate PEAK"
            if row.get("candidate_peak_total", 0) else ""
        ),
        axis=1,
    )
    return grouped


def build_player_name_resolver(athletes: pd.DataFrame, aliases: pd.DataFrame | None = None) -> dict[str, dict[str, str]]:
    """Map coach/legacy names and aliases to the canonical athlete display key."""
    resolver: dict[str, dict[str, str]] = {}
    if athletes.empty:
        return resolver

    athlete_cols = ["id", "display_name", "first_name", "last_name"]
    available_cols = [c for c in athlete_cols if c in athletes.columns]
    athlete_lookup = athletes[available_cols].copy()
    athlete_lookup["canonical_player"] = athlete_lookup.get("display_name", "").fillna("")
    fallback_name = (
        athlete_lookup.get("first_name", "").fillna("").astype(str)
        + " "
        + athlete_lookup.get("last_name", "").fillna("").astype(str)
    ).str.strip()
    athlete_lookup["canonical_player"] = athlete_lookup["canonical_player"].where(
        athlete_lookup["canonical_player"].astype(str).str.strip().ne(""),
        fallback_name,
    )
    athlete_lookup["canonical_player_key"] = athlete_lookup["canonical_player"].map(normalize_name)

    def add(raw_name: str, row: pd.Series, method: str, overwrite: bool = False) -> None:
        key = normalize_name(raw_name)
        if not key or (key in resolver and not overwrite):
            return
        resolver[key] = {
            "player_key": row["canonical_player_key"],
            "player": row["canonical_player"],
            "match_method": method,
        }

    for _, row in athlete_lookup.iterrows():
        add(row.get("display_name", ""), row, "athlete.display_name")
        full_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        add(full_name, row, "athlete.full_name")

    if aliases is not None and not aliases.empty:
        active_aliases = aliases.copy()
        if "is_active" in active_aliases.columns:
            active_aliases = active_aliases[active_aliases["is_active"].fillna(True).astype(bool)]
        if {"athlete_id", "alias_name"}.issubset(active_aliases.columns):
            alias_rows = active_aliases.merge(
                athlete_lookup,
                left_on="athlete_id",
                right_on="id",
                how="left",
                suffixes=("_alias", ""),
            )
            for _, row in alias_rows.iterrows():
                method_parts = ["athlete_alias"]
                if row.get("source_system"):
                    method_parts.append(str(row["source_system"]))
                if row.get("alias_type"):
                    method_parts.append(str(row["alias_type"]))
                add(row.get("alias_name", ""), row, ":".join(method_parts), overwrite=True)

    return resolver


def resolve_score_player_names(df: pd.DataFrame, source_prefix: str, resolver: dict[str, dict[str, str]]) -> pd.DataFrame:
    df = df.copy()
    raw_col = f"{source_prefix}_player_raw"
    resolved_col = f"{source_prefix}_player_resolved"
    method_col = f"{source_prefix}_player_match_method"

    def resolve(name: str) -> pd.Series:
        raw_key = normalize_name(name)
        match = resolver.get(raw_key)
        if match:
            return pd.Series({
                "player_key": match["player_key"],
                resolved_col: match["player"],
                method_col: match["match_method"],
            })
        return pd.Series({
            "player_key": raw_key,
            resolved_col: name,
            method_col: "unmatched",
        })

    resolved = df[raw_col].apply(resolve)
    return pd.concat([df, resolved], axis=1)


def build_event_trace(tables: dict[str, pd.DataFrame], version: str) -> pd.DataFrame:
    events = tables["athlete_event"].copy()
    if events.empty:
        return pd.DataFrame()

    athletes = tables["athlete"]
    metrics = tables["metric_definition"]
    categories = tables["metric_category"]
    sessions = tables["session"]
    matches = tables["match"]
    weights = latest_weights(tables["metric_weight"], version)
    sources = tables.get("data_source", pd.DataFrame())
    metric_map = load_wyscout_metric_map()
    peak_normalization = load_peak_normalization()
    peak_rules_by_key = {
        str(row["raw_label_key"]): row
        for _, row in peak_normalization.iterrows()
        if str(row.get("raw_label_key", "")).strip()
    }

    metric_lookup = metrics[["id", "category_id", "name", "peak_phase", "aset_letter"]].copy()
    metric_lookup["metric_key"] = metric_lookup["name"].map(normalize_metric_name)
    metric_lookup = metric_lookup.merge(
        categories[["id", "code", "label"]].rename(columns={"id": "category_id", "code": "metric_category_code", "label": "metric_category_label"}),
        on="category_id", how="left",
    )

    df = events.merge(
        athletes[["id", "display_name", "first_name", "last_name", "position", "position_group"]],
        left_on="athlete_id", right_on="id", how="left", suffixes=("", "_athlete"),
    )
    df = df.merge(
        metric_lookup.rename(columns={
            "id": "raw_metric_id",
            "name": "raw_metric_name",
            "metric_category_code": "raw_category_code",
            "metric_category_label": "raw_category_label",
        })[["raw_metric_id", "raw_metric_name", "raw_category_code", "raw_category_label"]],
        left_on="metric_id", right_on="raw_metric_id", how="left",
    )
    if not sources.empty:
        df = df.merge(
            sources[["id", "name", "platform", "source_priority"]].rename(columns={"id": "source_id", "name": "source_name"}),
            on="source_id", how="left",
        )
    else:
        df["platform"] = ""
        df["source_name"] = ""

    df["raw_metric_key"] = df["raw_metric_name"].map(normalize_metric_name)
    df = df.merge(metric_map, on="raw_metric_key", how="left")
    df["mapping_status"] = df["mapping_status"].fillna("unmapped")
    df["mapping_notes"] = df["mapping_notes"].fillna("")
    df["mapped_metric_name"] = df["mapped_metric_name"].fillna("")

    df["scoring_metric_name"] = df["mapped_metric_name"].where(df["mapped_metric_name"].ne(""), df["raw_metric_name"])
    df["scoring_metric_key"] = df["scoring_metric_name"].map(normalize_metric_name)
    df = df.merge(
        metric_lookup.rename(columns={
            "id": "scoring_metric_id",
            "name": "scoring_metric_definition_name",
            "metric_category_code": "scoring_category_code",
            "metric_category_label": "scoring_category_label",
        })[["scoring_metric_id", "scoring_metric_definition_name", "scoring_category_code", "scoring_category_label", "metric_key"]],
        left_on="scoring_metric_key", right_on="metric_key", how="left",
    )

    df = df.merge(
        weights[["id", "metric_id", "weight", "is_multiplier", "version"]].rename(columns={"id": "weight_id", "metric_id": "scoring_metric_id"}),
        on="scoring_metric_id", how="left",
    )
    df = df.merge(
        sessions[["id", "session_date", "season", "competition", "venue"]].rename(columns={"id": "session_id"}),
        on="session_id", how="left",
    )
    if not matches.empty:
        df = df.merge(
            matches[["session_id", "result", "goals_for", "goals_against"]],
            on="session_id", how="left",
        )

    df["player"] = df["display_name"].fillna((df["first_name"].fillna("") + " " + df["last_name"].fillna("")).str.strip())
    df["metric_name"] = df["scoring_metric_name"]
    df["category_code"] = df["scoring_category_code"].fillna(df["raw_category_code"])
    mapped_bucket = df["mapped_score_bucket"].fillna("")
    df["score_bucket"] = mapped_bucket.where(mapped_bucket.ne(""), df.apply(lambda r: score_bucket(r.get("category_code"), r.get("metric_name")), axis=1))
    df["raw_value"] = pd.to_numeric(df["raw_value"], errors="coerce").fillna(1.0)
    df["weight_missing"] = df["weight"].isna()
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
    df["event_score"] = df["raw_value"] * df["weight"]
    candidate_peak = df.apply(lambda row: candidate_peak_event(row, peak_rules_by_key), axis=1)
    df = pd.concat([df, candidate_peak], axis=1)
    df["calculation_note"] = ""
    multiplier_mask = df["is_multiplier"].eq(True)
    df.loc[multiplier_mask, "calculation_note"] = "multiplier weight treated as additive for trace; review formula"
    df.loc[df["scoring_metric_id"].isna(), "calculation_note"] = (
        df.loc[df["scoring_metric_id"].isna(), "calculation_note"]
        .where(df.loc[df["scoring_metric_id"].isna(), "calculation_note"].eq(""), df.loc[df["scoring_metric_id"].isna(), "calculation_note"] + "; ")
        + "mapped COUG metric not found in metric_definition"
    )
    df.loc[df["weight_missing"], "calculation_note"] = (
        df.loc[df["weight_missing"], "calculation_note"]
        .where(df.loc[df["weight_missing"], "calculation_note"].eq(""), df.loc[df["weight_missing"], "calculation_note"] + "; ")
        + "missing metric_weight for selected version"
    )
    df["player_key"] = df["player"].map(normalize_name)

    cols = [
        "session_id", "session_date", "season", "competition", "venue", "player", "player_key",
        "position", "position_group", "raw_metric_name", "scoring_metric_name", "metric_name",
        "raw_category_code", "category_code", "score_bucket", "mapping_status", "mapping_notes",
        "raw_value", "weight", "weight_missing", "event_score", "is_multiplier", "event_time",
        "candidate_peak_metric", "candidate_peak_phase", "candidate_peak_weight",
        "candidate_peak_score", "candidate_advance_action", "candidate_advance_threshold_count",
        "candidate_advance_threshold_score", "candidate_peak_model", "candidate_peak_note",
        "peak_score_policy", "peak_requires_success", "peak_success_rule",
        "peak_double_count_priority", "peak_pass_threshold_rule", "peak_official_status",
        "peak_implementation_status",
        "collection_method", "manually_tagged", "coach_confirmed", "source_name", "platform",
        "raw_value_context", "calculation_note",
    ]
    return df[[c for c in cols if c in df.columns]].sort_values(["session_date", "player", "score_bucket", "raw_metric_name"])

def summarize_trace(trace: pd.DataFrame) -> pd.DataFrame:
    if trace.empty:
        return pd.DataFrame()
    pivot = (
        trace.pivot_table(
            index=["session_id", "session_date", "season", "player", "player_key"],
            columns="score_bucket",
            values="event_score",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    for col in ["aset", "peak", "set_piece", "positional", "load", "other"]:
        if col not in pivot.columns:
            pivot[col] = 0.0
    counts = trace.groupby(["session_id", "player_key"]).size().rename("event_count").reset_index()
    pivot = pivot.merge(counts, on=["session_id", "player_key"], how="left")
    if "candidate_peak_score" in trace.columns:
        candidate_peak = (
            trace.groupby(["session_id", "player_key"])
            .agg(
                candidate_base_peak_score=("candidate_peak_score", "sum"),
                candidate_advance_actions=("candidate_advance_action", "sum"),
                candidate_advance_threshold_count=("candidate_advance_threshold_count", "max"),
                candidate_advance_threshold_score=("candidate_advance_threshold_score", "max"),
            )
            .reset_index()
        )
        candidate_peak["candidate_advance_threshold_count"] = (
            pd.to_numeric(candidate_peak["candidate_advance_threshold_count"], errors="coerce")
            .fillna(ADVANCE_ACTIONS_PER_CREDIT)
        )
        candidate_peak["candidate_advance_threshold_score"] = (
            pd.to_numeric(candidate_peak["candidate_advance_threshold_score"], errors="coerce")
            .fillna(ADVANCE_CREDIT_WEIGHT)
        )
        candidate_peak["candidate_advance_score"] = (
            candidate_peak["candidate_advance_actions"] // candidate_peak["candidate_advance_threshold_count"]
        ) * candidate_peak["candidate_advance_threshold_score"]
        candidate_peak["candidate_peak_score"] = (
            candidate_peak["candidate_base_peak_score"] + candidate_peak["candidate_advance_score"]
        )
    else:
        candidate_peak = pd.DataFrame(columns=[
            "session_id", "player_key", "candidate_base_peak_score",
            "candidate_advance_actions", "candidate_advance_threshold_count",
            "candidate_advance_threshold_score", "candidate_advance_score", "candidate_peak_score",
        ])
    pivot = pivot.merge(candidate_peak, on=["session_id", "player_key"], how="left")
    for col in [
        "candidate_base_peak_score", "candidate_advance_actions",
        "candidate_advance_threshold_count", "candidate_advance_threshold_score",
        "candidate_advance_score", "candidate_peak_score",
    ]:
        pivot[col] = pd.to_numeric(pivot[col], errors="coerce").fillna(0.0)
    score_cols = ["aset", "peak", "set_piece", "positional", "load", "other"]
    pivot["pipeline_total"] = pivot[score_cols].sum(axis=1)
    pivot["candidate_total_score"] = pivot["pipeline_total"] - pivot["peak"] + pivot["candidate_peak_score"]
    pivot["candidate_peak_model"] = CANDIDATE_PEAK_MODEL
    return pivot.rename(columns={
        "aset": "pipeline_aset",
        "peak": "pipeline_peak",
        "set_piece": "pipeline_set_piece",
        "positional": "pipeline_positional",
        "load": "pipeline_load",
        "other": "pipeline_other",
    })


def find_score_files(season: str, slug: str) -> ScoreFiles:
    paths = get_source_paths()
    legacy = paths.legacy_data_outputs_dir / str(season) / slug / f"{slug}_coug_scores.csv"

    date_key = slug_date(slug).replace("-", "_")
    opponent_key = "".join(part.capitalize() for part in slug_opponent(slug).split("_"))
    pdf_candidates = [
        paths.parsed_outputs_dir / str(season) / slug / f"coug_table_{date_key}_{opponent_key}.csv",
        paths.parsed_outputs_dir / str(season) / "coug_table" / f"coug_table_{date_key}_{opponent_key}.csv",
    ]
    pdf = next((p for p in pdf_candidates if p.exists()), None)
    return ScoreFiles(legacy if legacy.exists() else None, pdf)


def read_legacy_scores(path: Path, resolver: dict[str, dict[str, str]]) -> pd.DataFrame:
    df = pd.read_csv(path)
    out = pd.DataFrame({
        "legacy_player_raw": df["player"],
        "legacy_aset": pd.to_numeric(df.get("aset"), errors="coerce"),
        "legacy_peak": pd.to_numeric(df.get("peak"), errors="coerce"),
        "legacy_total": pd.to_numeric(df.get("total"), errors="coerce"),
        "legacy_event_count": pd.to_numeric(df.get("event_count"), errors="coerce"),
        "legacy_aset_breakdown": df.get("aset_breakdown"),
        "legacy_peak_breakdown": df.get("peak_breakdown"),
        "legacy_weights_version": df.get("weights_version"),
        "legacy_spiideo_included": df.get("spiideo_included"),
    })
    return resolve_score_player_names(out, "legacy", resolver)


def read_pdf_scores(path: Path, resolver: dict[str, dict[str, str]]) -> pd.DataFrame:
    df = pd.read_csv(path)
    out = pd.DataFrame({
        "pdf_player_raw": df["player"],
        "pdf_aset": pd.to_numeric(df.get("aset_score"), errors="coerce"),
        "pdf_peak": pd.to_numeric(df.get("peak_score"), errors="coerce"),
        "pdf_set_piece": pd.to_numeric(df.get("set_score"), errors="coerce"),
        "pdf_total": pd.to_numeric(df.get("total_score"), errors="coerce"),
    })
    return resolve_score_player_names(out, "pdf", resolver)


def compare_scores(summary: pd.DataFrame, season: str, slug: str, resolver: dict[str, dict[str, str]]) -> pd.DataFrame:
    files = find_score_files(season, slug)
    date = slug_date(slug)
    match_summary = summary[summary["session_date"].astype(str) == date].copy()

    compare = match_summary.copy()
    if files.legacy_csv:
        compare = compare.merge(read_legacy_scores(files.legacy_csv, resolver), on="player_key", how="outer")
    if files.pdf_csv:
        compare = compare.merge(read_pdf_scores(files.pdf_csv, resolver), on="player_key", how="outer")

    compare["slug"] = slug
    compare["legacy_source_file"] = str(files.legacy_csv) if files.legacy_csv else ""
    compare["pdf_source_file"] = str(files.pdf_csv) if files.pdf_csv else ""

    for old, new in [("legacy_aset", "pipeline_aset"), ("legacy_peak", "pipeline_peak"), ("legacy_peak", "candidate_peak_score"), ("legacy_total", "pipeline_total"), ("legacy_total", "candidate_total_score"), ("pdf_aset", "pipeline_aset"), ("pdf_peak", "pipeline_peak"), ("pdf_peak", "candidate_peak_score"), ("pdf_total", "pipeline_total"), ("pdf_total", "candidate_total_score")]:
        if old in compare.columns and new in compare.columns:
            compare[f"delta_{new}_vs_{old}"] = compare[new].fillna(0) - compare[old].fillna(0)

    return compare


def write_outputs(trace: pd.DataFrame, summary: pd.DataFrame, explainer: pd.DataFrame, comparisons: list[pd.DataFrame], season: str, slug_label: str, dry_run: bool) -> None:
    paths = get_source_paths()
    out_dir = paths.reports_dir / "score_reconciliation" / str(season)
    if dry_run:
        print(f"[DRY RUN] Would write reports to {out_dir}")
        print(f"[DRY RUN] Event trace rows: {len(trace)} | Summary rows: {len(summary)} | Explainer rows: {len(explainer)}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / f"{slug_label}_event_score_trace.csv"
    summary_path = out_dir / f"{slug_label}_pipeline_score_summary.csv"
    explain_path = out_dir / f"{slug_label}_score_explainer.csv"
    compare_path = out_dir / f"{slug_label}_score_reconciliation.csv"

    trace.to_csv(trace_path, index=False)
    summary.to_csv(summary_path, index=False)
    explainer.to_csv(explain_path, index=False)
    if comparisons:
        pd.concat(comparisons, ignore_index=True, sort=False).to_csv(compare_path, index=False)
    else:
        pd.DataFrame().to_csv(compare_path, index=False)

    print(f"Wrote {trace_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {explain_path}")
    print(f"Wrote {compare_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile event-derived COUG scores against legacy/PDF score files")
    parser.add_argument("--season", default="2025")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--weight-version", default="trial_1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = get_client()
    table_names = ["athlete_event", "athlete", "metric_definition", "metric_category", "metric_weight", "session", "match", "data_source"]
    tables = {name: fetch_all(client, name) for name in table_names}
    tables["athlete_alias"] = fetch_optional(client, "athlete_alias")
    print("Fetched rows: " + ", ".join(f"{name}={len(df)}" for name, df in tables.items()))

    trace = build_event_trace(tables, args.weight_version)
    if trace.empty:
        print("No athlete_event rows found; cannot build event-derived score trace yet.")
        return

    summary = summarize_trace(trace)
    summary = summary[summary["season"].astype(str) == str(args.season)].copy()

    paths = get_source_paths()
    if args.slug:
        slugs = [args.slug]
        selected_dates = {slug_date(args.slug)}
        trace_out = trace[trace["session_date"].astype(str).isin(selected_dates)].copy()
        summary_out = summary[summary["session_date"].astype(str).isin(selected_dates)].copy()
    else:
        season_dir = paths.matches_dir / str(args.season)
        slugs = sorted(p.name for p in season_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
        trace_out = trace[trace["season"].astype(str) == str(args.season)].copy()
        summary_out = summary

    explainer_out = build_score_explainer(trace_out)
    resolver = build_player_name_resolver(tables["athlete"], tables.get("athlete_alias"))
    comparisons = [compare_scores(summary, args.season, slug, resolver) for slug in slugs]
    slug_label = args.slug if args.slug else "season"
    write_outputs(trace_out, summary_out, explainer_out, comparisons, args.season, slug_label, args.dry_run)


if __name__ == "__main__":
    main()
