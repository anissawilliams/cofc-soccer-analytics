import numpy as np
import pandas as pd
from ingest import load_matches, build_match_features
from config import TEAM_INGEST_DIR

np.random.seed(42)
ingest_dir = TEAM_INGEST_DIR

def simulate_match(xg_home, xg_away, n_simulations=10000):
    """
    Simulate a match n times using Poisson-distributed goal sampling.

    In football, goals scored follow a Poisson distribution —
    this is the industry-standard approach used by professional
    prediction models including those at betting firms and clubs.

    Args:
        xg_home: Expected goals for home team
        xg_away: Expected goals for away team
        n_simulations: Number of Monte Carlo iterations

    Returns:
        dict with win/draw/loss probabilities and score distribution
    """
    # Sample goals from Poisson distribution for each simulation
    home_goals = np.random.poisson(xg_home, n_simulations)
    away_goals = np.random.poisson(xg_away, n_simulations)

    # Determine outcomes
    home_wins = np.sum(home_goals > away_goals)
    draws = np.sum(home_goals == away_goals)
    away_wins = np.sum(home_goals < away_goals)

    # Most common scorelines
    scores = pd.Series(list(zip(home_goals, away_goals)))
    top_scores = scores.value_counts().head(5)

    return {
        'home_win_pct': home_wins / n_simulations,
        'draw_pct': draws / n_simulations,
        'away_win_pct': away_wins / n_simulations,
        'avg_home_goals': home_goals.mean(),
        'avg_away_goals': away_goals.mean(),
        'top_scorelines': top_scores
    }


def simulate_season(features, n_simulations=10000):
    """
    Run Monte Carlo simulation for every match in the dataset
    and compare predicted probabilities to actual outcomes.
    """
    results = []

    for _, row in features.iterrows():
        sim = simulate_match(row['xg_cofc'], row['xg_opp'], n_simulations)

        # From CofC perspective: home = CofC, away = opponent
        # (we already built features from CofC's POV)
        actual = row['result']

        # What probability did we assign to the actual outcome?
        if actual == 'W':
            assigned_prob = sim['home_win_pct']
        elif actual == 'D':
            assigned_prob = sim['draw_pct']
        else:
            assigned_prob = sim['away_win_pct']

        # Predicted outcome = highest probability
        probs = {
            'W': sim['home_win_pct'],
            'D': sim['draw_pct'],
            'L': sim['away_win_pct']
        }
        predicted = max(probs, key=probs.get)

        results.append({
            'date': row['date'],
            'match': row['match'],
            'xg_cofc': row['xg_cofc'],
            'xg_opp': row['xg_opp'],
            'win_prob': sim['home_win_pct'],
            'draw_prob': sim['draw_pct'],
            'loss_prob': sim['away_win_pct'],
            'predicted': predicted,
            'actual': actual,
            'correct': predicted == actual,
            'prob_assigned_to_actual': assigned_prob,
        })

    return pd.DataFrame(results)


def simulate_upcoming_match(cofc_xg, opp_xg, opp_name, n_simulations=10000):
    """
    Simulate a single upcoming match and print a scouting report.
    """
    sim = simulate_match(cofc_xg, opp_xg, n_simulations)

    print(f"\n{'=' * 50}")
    print(f"MATCH SIMULATION: CofC vs {opp_name}")
    print(f"CofC xG: {cofc_xg:.2f} | {opp_name} xG: {opp_xg:.2f}")
    print(f"Simulations: {n_simulations:,}")
    print(f"{'=' * 50}")
    print(f"  CofC Win:  {sim['home_win_pct']:.1%}")
    print(f"  Draw:      {sim['draw_pct']:.1%}")
    print(f"  CofC Loss: {sim['away_win_pct']:.1%}")
    print(f"\n  Avg Score: CofC {sim['avg_home_goals']:.1f} - {sim['avg_away_goals']:.1f} {opp_name}")
    print(f"\n  Most Likely Scorelines:")
    for score, count in sim['top_scorelines'].items():
        print(f"    {score[0]}-{score[1]}: {count / n_simulations:.1%}")
    print(f"{'=' * 50}\n")

    return sim


if __name__ == '__main__':
    # Load real CofC data
    print("Loading match data...")
    df = load_matches(ingest_dir + 'cofc_matches_2025.xlsx')
    features = build_match_features(df)

    # Run season simulation
    print("Running Monte Carlo simulation for all matches...")
    results = simulate_season(features, n_simulations=10000)

    # Accuracy
    accuracy = results['correct'].mean()
    print(f"\nMonte Carlo Prediction Accuracy: {accuracy:.1%}")
    print(f"(Baseline logistic regression was 62.5%)")

    # Average probability assigned to actual outcome
    # Higher = model was more confident about correct outcomes
    avg_prob = results['prob_assigned_to_actual'].mean()
    print(f"Avg probability assigned to actual outcome: {avg_prob:.1%}")

    print("\nMatch-by-Match Results:")
    print(results[[
        'date', 'match', 'xg_cofc', 'xg_opp',
        'win_prob', 'draw_prob', 'loss_prob',
        'predicted', 'actual', 'correct'
    ]].to_string(index=False))

    # Demo: simulate a hypothetical next match
    # Using CofC's season average xG vs a typical opponent
    avg_cofc_xg = features['xg_cofc'].mean()
    avg_opp_xg = features['xg_opp'].mean()
    simulate_upcoming_match(avg_cofc_xg, avg_opp_xg, "Next Opponent", n_simulations=10000)