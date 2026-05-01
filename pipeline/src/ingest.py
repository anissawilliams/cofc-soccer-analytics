import pandas as pd
import numpy as np

ingest_dir = '../data/raw/'

def load_matches(path):
    # Read raw, skip the first 3 rows (header + 2 average rows)
    df = pd.read_excel(path, header=None, skiprows=3)

    df.columns = [
        'date', 'match', 'competition', 'duration', 'team', 'scheme',
        'goals', 'xg',
        'shots', 'shots_on_target', 'shot_conversion_pct',
        'passes', 'passes_accurate', 'pass_accuracy_pct',
        'possession_pct',
        'losses', 'losses_low', 'losses_mid', 'losses_high',
        'recoveries', 'recoveries_low', 'recoveries_mid', 'recoveries_high',
        'duels', 'duels_won', 'duel_win_pct'
    ]

    # Drop rows with no date (shouldn't be any but just in case)
    df = df[df['date'].notna()].copy()
    df['date'] = pd.to_datetime(df['date'])

    # Extract result from match string e.g. "Charleston Cougars - UNCW Seahawks 2:1"
    def parse_result(row):
        match_str = str(row['match'])
        team = str(row['team'])
        try:
            score_part = match_str.split(' ')[-1]  # "2:1"
            home_team = match_str.split(' - ')[0].strip()
            score = score_part.split(':')
            home_goals = int(score[0])
            away_goals = int(score[1])

            is_home = home_team == team
            team_goals = home_goals if is_home else away_goals
            opp_goals = away_goals if is_home else home_goals

            if team_goals > opp_goals:
                return 'W'
            elif team_goals < opp_goals:
                return 'L'
            else:
                return 'D'
        except:
            return None

    df['result'] = df.apply(parse_result, axis=1)
    df['is_cofc'] = df['team'] == 'Charleston Cougars'

    return df


def build_match_features(df):
    """
    For each match, build a feature row from CofC's perspective.
    Features: CofC stats vs Opponent stats side by side.
    Target: result (W/D/L)
    """
    cofc = df[df['is_cofc']].copy().reset_index(drop=True)
    opps = df[~df['is_cofc']].copy().reset_index(drop=True)

    # Merge on match + date
    merged = cofc.merge(
        opps[['match', 'date', 'goals', 'xg', 'shots', 'shots_on_target',
              'pass_accuracy_pct', 'possession_pct', 'recoveries', 'duels_won']],
        on=['match', 'date'],
        suffixes=('_cofc', '_opp')
    )

    # Feature engineering
    merged['xg_diff'] = merged['xg_cofc'] - merged['xg_opp']
    merged['possession_diff'] = merged['possession_pct_cofc'] - merged['possession_pct_opp']
    merged['shot_diff'] = merged['shots_cofc'] - merged['shots_opp']
    merged['pass_acc_diff'] = merged['pass_accuracy_pct_cofc'] - merged['pass_accuracy_pct_opp']
    merged['recovery_diff'] = merged['recoveries_cofc'] - merged['recoveries_opp']

    return merged


if __name__ == '__main__':
    df = load_matches(ingest_dir + 'cofc_matches_2025.xlsx')
    print(f"Total rows loaded: {len(df)}")
    print(f"CofC matches: {df['is_cofc'].sum()}")
    print(f"\nResults distribution:")
    print(df[df['is_cofc']]['result'].value_counts())

    features = build_match_features(df)
    print(f"\nFeature matrix shape: {features.shape}")
    print(f"\nSample features:")
    print(features[['date', 'match', 'result', 'xg_diff', 'possession_diff', 'shot_diff']].to_string())