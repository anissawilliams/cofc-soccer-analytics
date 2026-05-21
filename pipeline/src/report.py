import pandas as pd
import numpy as np
from datetime import datetime
from ingest import load_matches, build_match_features
from simulate import simulate_match
from config import TEAM_INGEST_DIR

ingest_dir = TEAM_INGEST_DIR

def get_team_season_profile(features, team_col='xg_cofc'):
    """Calculate season averages for a team."""
    return {
        'avg_xg_for':       features['xg_cofc'].mean(),
        'avg_xg_against':   features['xg_opp'].mean(),
        'avg_shots_for':    features['shots_cofc'].mean(),
        'avg_shots_against':features['shots_opp'].mean(),
        'avg_possession':   features['possession_pct_cofc'].mean(),
        'avg_pass_acc':     features['pass_accuracy_pct_cofc'].mean(),
        'avg_recoveries':   features['recoveries_cofc'].mean(),
        'wins':             (features['result'] == 'W').sum(),
        'draws':            (features['result'] == 'D').sum(),
        'losses':           (features['result'] == 'L').sum(),
        'matches':          len(features),
    }


def get_recent_form(features, n=5):
    """Get last N match results."""
    recent = features.sort_values('date', ascending=False).head(n)
    form = ''.join(recent['result'].tolist())
    return form, recent


def generate_scouting_report(
    features,
    opponent_name,
    opponent_xg_for,
    opponent_xg_against,
    opponent_pass_acc,
    opponent_possession,
    match_date=None,
    n_simulations=10000
):
    """
    Generate a pre-match scouting report combining:
    - CofC season profile
    - Opponent profile (from their recent data)
    - Monte Carlo match simulation
    - Key tactical insights
    """

    if match_date is None:
        match_date = datetime.today().strftime('%Y-%m-%d')

    profile = get_team_season_profile(features)
    form_str, recent = get_recent_form(features)

    # Run simulation using opponent's avg xG for as their threat level
    sim = simulate_match(
        xg_home=profile['avg_xg_for'],
        xg_away=opponent_xg_for,
        n_simulations=n_simulations
    )

    # Key matchup flags
    possession_advantage = profile['avg_possession'] > opponent_possession
    passing_advantage = profile['avg_pass_acc'] > opponent_pass_acc
    xg_advantage = profile['avg_xg_for'] > opponent_xg_for

    report = []
    report.append("=" * 60)
    report.append(f"  PRE-MATCH SCOUTING REPORT")
    report.append(f"  College of Charleston Cougars")
    report.append(f"  vs {opponent_name}")
    report.append(f"  {match_date}")
    report.append("=" * 60)

    report.append("\n📊 COFC SEASON PROFILE")
    report.append(f"  Record:          {profile['wins']}W - {profile['draws']}D - {profile['losses']}L")
    report.append(f"  Recent Form:     {form_str}")
    report.append(f"  Avg xG For:      {profile['avg_xg_for']:.2f}")
    report.append(f"  Avg xG Against:  {profile['avg_xg_against']:.2f}")
    report.append(f"  Avg Possession:  {profile['avg_possession']:.1f}%")
    report.append(f"  Avg Pass Acc:    {profile['avg_pass_acc']:.1f}%")
    report.append(f"  Avg Recoveries:  {profile['avg_recoveries']:.1f}")

    report.append(f"\n🔎 OPPONENT PROFILE: {opponent_name}")
    report.append(f"  Avg xG For:      {opponent_xg_for:.2f}")
    report.append(f"  Avg xG Against:  {opponent_xg_against:.2f}")
    report.append(f"  Avg Possession:  {opponent_possession:.1f}%")
    report.append(f"  Avg Pass Acc:    {opponent_pass_acc:.1f}%")

    report.append(f"\n🎲 MONTE CARLO SIMULATION ({n_simulations:,} iterations)")
    report.append(f"  CofC Win:        {sim['home_win_pct']:.1%}")
    report.append(f"  Draw:            {sim['draw_pct']:.1%}")
    report.append(f"  CofC Loss:       {sim['away_win_pct']:.1%}")
    report.append(f"  Expected Score:  CofC {sim['avg_home_goals']:.1f} - {sim['avg_away_goals']:.1f} {opponent_name}")

    report.append(f"\n  Most Likely Scorelines:")
    for score, count in sim['top_scorelines'].items():
        bar = '█' * int((count / n_simulations) * 50)
        report.append(f"    {score[0]}-{score[1]}:  {bar} {count/n_simulations:.1%}")

    report.append(f"\n⚡ KEY MATCHUP INSIGHTS")
    report.append(f"  Possession:  {'CofC advantage' if possession_advantage else 'Opponent advantage'} "
                  f"({profile['avg_possession']:.1f}% vs {opponent_possession:.1f}%)")
    report.append(f"  Passing:     {'CofC advantage' if passing_advantage else 'Opponent advantage'} "
                  f"({profile['avg_pass_acc']:.1f}% vs {opponent_pass_acc:.1f}%)")
    report.append(f"  xG:          {'CofC advantage' if xg_advantage else 'Opponent advantage'} "
                  f"({profile['avg_xg_for']:.2f} vs {opponent_xg_for:.2f})")

    report.append(f"\n📋 TACTICAL NOTES")
    if profile['avg_xg_for'] < profile['avg_xg_against']:
        report.append("  ⚠ CofC generating less xG than conceding this season.")
        report.append("    Focus: improve chance creation in final third.")
    else:
        report.append("  ✓ CofC generating more xG than conceding — strong attacking form.")

    xg_overperform = profile['wins'] - round(profile['avg_xg_for'] * profile['matches'] /
                     (profile['avg_xg_for'] + profile['avg_xg_against'] + 0.001))
    if xg_overperform > 0:
        report.append(f"  ✓ CofC overperforming xG model by ~{xg_overperform} wins — "
                      f"strong finishing or defensive organization.")
    elif xg_overperform < 0:
        report.append(f"  ⚠ CofC underperforming xG model — regression to mean possible.")

    if profile['avg_pass_acc'] > 75:
        report.append(f"  ✓ Pass accuracy ({profile['avg_pass_acc']:.1f}%) is a key strength — "
                      f"most predictive feature in the model.")

    report.append(f"\n📅 RECENT MATCHES")
    for _, row in recent.iterrows():
        result_icon = '✓' if row['result'] == 'W' else ('~' if row['result'] == 'D' else '✗')
        report.append(f"  {result_icon} {row['date'].strftime('%m/%d')} | "
                      f"{row['result']} | xG {row['xg_cofc']:.2f}-{row['xg_opp']:.2f} | "
                      f"{row['match'].split(' - ')[1] if ' - ' in row['match'] else row['match']}")

    report.append("\n" + "=" * 60)

    return '\n'.join(report)


if __name__ == '__main__':
    # Load CofC data
    df = load_matches(ingest_dir+'cofc_matches_2025.xlsx')
    features = build_match_features(df)

    # Demo: generate a report using season averages as "next opponent"
    # In production this would pull from the opponent's Wyscout data
    avg_xg = features['xg_opp'].mean()
    avg_pass = features['pass_accuracy_pct_opp'].mean()
    avg_poss = features['possession_pct_opp'].mean()
    avg_xg_against = features['xg_cofc'].mean()

    report = generate_scouting_report(
        features=features,
        opponent_name="William & Mary Tribe",
        opponent_xg_for=avg_xg,
        opponent_xg_against=avg_xg_against,
        opponent_pass_acc=avg_pass,
        opponent_possession=avg_poss,
        match_date="2025-11-08",
        n_simulations=10000
    )

    print(report)

    # Save to file
    with open('../outputs/scouting_report_demo.txt', 'w') as f:
        f.write(report)
    print("\n✅ Report saved to outputs/scouting_report_demo.txt")