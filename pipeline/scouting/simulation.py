from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_match(
    team_xg: float,
    opponent_xg: float,
    n_simulations: int = 10000,
    random_state: int = 42,
) -> dict[str, object]:
    rng = np.random.default_rng(random_state)
    team_goals = rng.poisson(max(team_xg, 0.01), n_simulations)
    opponent_goals = rng.poisson(max(opponent_xg, 0.01), n_simulations)

    scorelines = pd.Series(list(zip(team_goals, opponent_goals))).value_counts().head(5)
    return {
        "win_prob": float(np.mean(team_goals > opponent_goals)),
        "draw_prob": float(np.mean(team_goals == opponent_goals)),
        "loss_prob": float(np.mean(team_goals < opponent_goals)),
        "avg_team_goals": float(np.mean(team_goals)),
        "avg_opponent_goals": float(np.mean(opponent_goals)),
        "top_scorelines": [
            {"scoreline": f"{score[0]}-{score[1]}", "probability": float(count / n_simulations)}
            for score, count in scorelines.items()
        ],
    }


def simulate_from_match_features(
    features: pd.DataFrame,
    n_simulations: int = 10000,
    random_state: int = 42,
) -> pd.DataFrame:
    rows = []
    for row_number, (_, row) in enumerate(features.iterrows()):
        sim = simulate_match(
            row["xg_cofc"],
            row["xg_opp"],
            n_simulations=n_simulations,
            random_state=random_state + row_number,
        )
        probs = {"W": sim["win_prob"], "D": sim["draw_prob"], "L": sim["loss_prob"]}
        predicted = max(probs, key=probs.get)
        rows.append(
            {
                "date": row["date"],
                "match": row["match"],
                "opponent": row.get("opponent"),
                "actual": row["result"],
                "predicted": predicted,
                "correct": predicted == row["result"],
                "xg_cofc": row["xg_cofc"],
                "xg_opp": row["xg_opp"],
                **{key: sim[key] for key in ["win_prob", "draw_prob", "loss_prob"]},
            }
        )
    return pd.DataFrame(rows)
