"""
simulate_bootstrap.py — Bootstrap uncertainty quantification for CofC match simulation
========================================================================================
Extends simulate.py with:
  1. bootstrap_xg()                  — resample season xG to generate uncertainty bounds
  2. simulate_match_with_uncertainty() — win/draw/loss probabilities with 95% CI
  3. leave_one_out_validation()      — honest accuracy estimate via LOO cross-validation
  4. bootstrap_season_report()       — full season report with uncertainty on every match

Why bootstrapping instead of a supervised classifier:
  With 15 matches, a supervised classifier (logistic regression, gradient boosting, etc.)
  would have severe overfitting risk and unreliable cross-validated accuracy estimates.
  Bootstrapping extends the existing Poisson/Monte Carlo model by quantifying uncertainty
  in the xG inputs themselves — without requiring more data than we have.

  Leave-one-out cross-validation gives an honest, unbiased accuracy estimate
  on a small dataset, since every match is used exactly once as a held-out test case.

Usage:
    from simulate_bootstrap import bootstrap_season_report, leave_one_out_validation
    from ingest import load_matches, build_match_features

    features = build_match_features(load_matches("cofc_matches_2025.xlsx"))
    loo_results = leave_one_out_validation(features)
    report = bootstrap_season_report(features)
"""

import numpy as np
import pandas as pd
from simulate import simulate_match

np.random.seed(42)


# ── 1. Bootstrap xG resampling ────────────────────────────────────────────────

def bootstrap_xg(
    xg_values: np.ndarray,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
) -> dict:
    """
    Resample a set of xG observations to quantify uncertainty in the mean.

    In a small sample (15 matches), the observed mean xG is an estimate
    of the true underlying rate. Bootstrapping gives us a distribution
    of plausible mean xG values, which we propagate into the simulation.

    Args:
        xg_values:   array of observed xG values (one per match)
        n_bootstrap: number of bootstrap resamples (default 1000)
        ci:          confidence interval width (default 0.95 = 95% CI)

    Returns:
        dict with mean, lower, upper bounds on xG
    """
    means = np.array([
        np.mean(np.random.choice(xg_values, size=len(xg_values), replace=True))
        for _ in range(n_bootstrap)
    ])
    alpha = (1 - ci) / 2
    return {
        "mean":  float(np.mean(means)),
        "lower": float(np.quantile(means, alpha)),
        "upper": float(np.quantile(means, 1 - alpha)),
        "std":   float(np.std(means)),
    }


# ── 2. Match simulation with uncertainty ──────────────────────────────────────

def simulate_match_with_uncertainty(
    cofc_xg: float,
    opp_xg: float,
    cofc_xg_std: float = 0.0,
    opp_xg_std: float  = 0.0,
    n_simulations: int = 10000,
    n_bootstrap: int   = 500,
    ci: float          = 0.95,
) -> dict:
    """
    Simulate a match with uncertainty bounds on outcome probabilities.

    If xG standard deviations are provided (from bootstrap_xg), the
    simulation draws a new xG value for each bootstrap iteration,
    producing a distribution of win/draw/loss probabilities rather
    than a single point estimate.

    Args:
        cofc_xg:       CofC expected goals (point estimate)
        opp_xg:        Opponent expected goals (point estimate)
        cofc_xg_std:   Std dev on CofC xG (from bootstrapping — 0 = no uncertainty)
        opp_xg_std:    Std dev on opponent xG (from bootstrapping — 0 = no uncertainty)
        n_simulations: Monte Carlo draws per bootstrap iteration
        n_bootstrap:   Number of bootstrap iterations
        ci:            Confidence interval width (default 0.95)

    Returns:
        dict with point estimates + CI bounds for win/draw/loss
    """
    alpha = (1 - ci) / 2

    win_probs  = []
    draw_probs = []
    loss_probs = []

    for _ in range(n_bootstrap):
        # Draw plausible xG values (if std > 0, add uncertainty)
        xg_c = max(0.01, np.random.normal(cofc_xg, cofc_xg_std) if cofc_xg_std > 0 else cofc_xg)
        xg_o = max(0.01, np.random.normal(opp_xg,  opp_xg_std)  if opp_xg_std  > 0 else opp_xg)

        sim = simulate_match(xg_c, xg_o, n_simulations)
        win_probs.append(sim["home_win_pct"])
        draw_probs.append(sim["draw_pct"])
        loss_probs.append(sim["away_win_pct"])

    win_probs  = np.array(win_probs)
    draw_probs = np.array(draw_probs)
    loss_probs = np.array(loss_probs)

    def ci_dict(arr, name):
        return {
            f"{name}":       float(np.mean(arr)),
            f"{name}_lower": float(np.quantile(arr, alpha)),
            f"{name}_upper": float(np.quantile(arr, 1 - alpha)),
        }

    result = {}
    result.update(ci_dict(win_probs,  "win_prob"))
    result.update(ci_dict(draw_probs, "draw_prob"))
    result.update(ci_dict(loss_probs, "loss_prob"))
    result["ci"] = ci
    result["n_bootstrap"] = n_bootstrap
    return result


# ── 3. Leave-one-out cross-validation ─────────────────────────────────────────

def leave_one_out_validation(
    features: pd.DataFrame,
    n_simulations: int = 10000,
) -> pd.DataFrame:
    """
    Leave-one-out cross-validation for the Poisson simulation.

    For each match i in the dataset:
      - Estimate xG rates from the remaining 14 matches
      - Simulate match i using those rates
      - Record whether the prediction was correct

    This gives an honest accuracy estimate that isn't inflated by
    training and testing on the same data — critical for a small
    dataset where train/test split would leave too few observations.

    Args:
        features:      DataFrame with columns: xg_cofc, xg_opp, result, match, date
        n_simulations: Monte Carlo draws per match

    Returns:
        DataFrame with per-match LOO predictions and accuracy summary
    """
    results = []

    for i in range(len(features)):
        # Hold out match i
        held_out = features.iloc[i]
        train    = features.drop(features.index[i])

        # Estimate xG rates from remaining matches
        # Use mean of training set as the base rate for this matchup
        cofc_xg_train = train["xg_cofc"].mean()
        opp_xg_train  = train["xg_opp"].mean()

        # Bootstrap uncertainty from training set
        cofc_boot = bootstrap_xg(train["xg_cofc"].values)
        opp_boot  = bootstrap_xg(train["xg_opp"].values)

        # Simulate the held-out match using training-derived rates
        sim = simulate_match_with_uncertainty(
            cofc_xg     = cofc_xg_train,
            opp_xg      = opp_xg_train,
            cofc_xg_std = cofc_boot["std"],
            opp_xg_std  = opp_boot["std"],
            n_simulations = n_simulations,
            n_bootstrap   = 200,  # lighter for LOO speed
        )

        # Prediction = highest probability outcome
        probs = {
            "W": sim["win_prob"],
            "D": sim["draw_prob"],
            "L": sim["loss_prob"],
        }
        predicted = max(probs, key=probs.get)
        actual    = held_out["result"]

        # Probability assigned to the actual outcome
        prob_actual = probs[actual]

        results.append({
            "date":            held_out["date"],
            "match":           held_out["match"],
            "actual":          actual,
            "predicted":       predicted,
            "correct":         predicted == actual,
            "win_prob":        sim["win_prob"],
            "win_prob_lower":  sim["win_prob_lower"],
            "win_prob_upper":  sim["win_prob_upper"],
            "draw_prob":       sim["draw_prob"],
            "loss_prob":       sim["loss_prob"],
            "prob_actual":     prob_actual,
            "cofc_xg_used":    cofc_xg_train,
            "opp_xg_used":     opp_xg_train,
            "actual_cofc_xg":  held_out["xg_cofc"],
            "actual_opp_xg":   held_out["xg_opp"],
        })

    df = pd.DataFrame(results)

    # Summary
    accuracy    = df["correct"].mean()
    avg_prob    = df["prob_actual"].mean()
    n_matches   = len(df)
    win_correct = df[df["actual"] == "W"]["correct"].mean() if (df["actual"] == "W").any() else None
    loss_correct= df[df["actual"] == "L"]["correct"].mean() if (df["actual"] == "L").any() else None
    draw_correct= df[df["actual"] == "D"]["correct"].mean() if (df["actual"] == "D").any() else None

    print(f"\n{'='*60}")
    print(f"LEAVE-ONE-OUT CROSS-VALIDATION — {n_matches} matches")
    print(f"{'='*60}")
    print(f"  Overall accuracy:      {accuracy:.1%}  ({df['correct'].sum()}/{n_matches} correct)")
    print(f"  Avg prob on actual:    {avg_prob:.1%}  (higher = more calibrated)")
    print(f"  Accuracy by outcome:")
    if win_correct  is not None: print(f"    Wins:   {win_correct:.1%}")
    if draw_correct is not None: print(f"    Draws:  {draw_correct:.1%}")
    if loss_correct is not None: print(f"    Losses: {loss_correct:.1%}")
    print(f"\n  Note: LOO uses season-average xG as the base rate for each")
    print(f"  held-out match. This is conservative — a real pre-match model")
    print(f"  would use opponent-specific xG, which requires more data.")
    print(f"{'='*60}\n")

    return df


# ── 4. Full season bootstrap report ───────────────────────────────────────────

def bootstrap_season_report(
    features: pd.DataFrame,
    n_simulations: int = 10000,
    n_bootstrap: int   = 500,
    ci: float          = 0.95,
) -> pd.DataFrame:
    """
    Run bootstrap simulation for every match in the season.
    Uses the full season's xG distribution to estimate uncertainty,
    then simulates each match with those uncertainty bounds.

    Unlike LOO, this uses ALL matches to estimate xG rates —
    it's useful for retrospective reporting, not prediction.

    Returns:
        DataFrame with per-match probabilities and CI bounds
    """
    cofc_boot = bootstrap_xg(features["xg_cofc"].values, n_bootstrap)
    opp_boot  = bootstrap_xg(features["xg_opp"].values,  n_bootstrap)

    print(f"Season xG — CofC: {cofc_boot['mean']:.2f} "
          f"[{cofc_boot['lower']:.2f}–{cofc_boot['upper']:.2f}] | "
          f"Opp: {opp_boot['mean']:.2f} "
          f"[{opp_boot['lower']:.2f}–{opp_boot['upper']:.2f}]")

    results = []
    for _, row in features.iterrows():
        sim = simulate_match_with_uncertainty(
            cofc_xg     = row["xg_cofc"],
            opp_xg      = row["xg_opp"],
            cofc_xg_std = cofc_boot["std"],
            opp_xg_std  = opp_boot["std"],
            n_simulations = n_simulations,
            n_bootstrap   = n_bootstrap,
            ci            = ci,
        )

        probs    = {"W": sim["win_prob"], "D": sim["draw_prob"], "L": sim["loss_prob"]}
        predicted = max(probs, key=probs.get)
        actual    = row["result"]

        results.append({
            "date":           row["date"],
            "match":          row["match"],
            "actual":         actual,
            "predicted":      predicted,
            "correct":        predicted == actual,
            "xg_cofc":        row["xg_cofc"],
            "xg_opp":         row["xg_opp"],
            **sim,
        })

    df = pd.DataFrame(results)
    accuracy = df["correct"].mean()

    print(f"\n{'='*60}")
    print(f"BOOTSTRAP SEASON REPORT ({int(ci*100)}% CI, {n_bootstrap} resamples)")
    print(f"{'='*60}")
    print(df[[
        "date", "match", "xg_cofc", "xg_opp",
        "win_prob", "win_prob_lower", "win_prob_upper",
        "draw_prob", "loss_prob", "predicted", "actual", "correct"
    ]].to_string(index=False))
    print(f"\n  Accuracy: {accuracy:.1%} ({df['correct'].sum()}/{len(df)})")
    print(f"{'='*60}\n")

    return df


# ── CLI / demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from ingest import load_matches, build_match_features
    from config import TEAM_INGEST_DIR

    print("Loading match data...")
    df       = load_matches(os.path.join(TEAM_INGEST_DIR, "cofc_matches_2025.xlsx"))
    features = build_match_features(df)

    print(f"\nLoaded {len(features)} matches\n")

    # Leave-one-out validation
    loo = leave_one_out_validation(features)

    # Full season bootstrap report
    report = bootstrap_season_report(features)

    # Save
    loo.to_csv("loo_validation_2025.csv", index=False)
    report.to_csv("bootstrap_season_2025.csv", index=False)
    print("Saved: loo_validation_2025.csv, bootstrap_season_2025.csv")