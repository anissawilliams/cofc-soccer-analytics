import re
import subprocess
import pandas as pd
from pathlib import Path
import warnings

from config import PLAYER_INGEST_DIR, COUG_TABLE_DIR

warnings.filterwarnings('ignore')

def file_helper(filename):
    match_name = filename.split('_')[3] # opponent name
    match_date = filename.split('players_', 1)[1].split('.pdf')[0]
    return match_name, match_date


def extract_page_text(pdf_path, page_num):
    """Extract text from a single page using pdftotext."""
    result = subprocess.run(
        ['pdftotext', '-layout', '-f', str(page_num), '-l', str(page_num), pdf_path, '-'],
        capture_output=True, text=True
    )
    return result.stdout


def parse_player_name(text):
    """Extract player name from page header."""
    # Pattern: "PLAYER IN MATCH    FirstName. LastName"
    match = re.search(r'P L AY E R I N M AT C H\s+([A-Z]\.\s+\w+)', text)
    if match:
        return match.group(1).strip()
    # Goalkeeper pattern
    match = re.search(r'G O A L K E E P E R I N M AT C H\s+([A-Z]\.\s+\w+)', text)
    if match:
        return match.group(1).strip()
    return None


def parse_match_info(text):
    """Extract match info from page header."""
    match = re.search(r'Charleston Cougars (\d+) [–-] (\d+) (\w.*?)\s*\((\d{2}\.\d{2}\.\d{4})\)', text)
    if match:
        return {
            'cofc_goals': int(match.group(1)),
            'opp_goals': int(match.group(2)),
            'opponent': match.group(3).strip(),
            'date': match.group(4)
        }
    return {}


def parse_stat_value(text, stat_name):
    """
    Extract a stat value from the two-column layout.
    Handles formats like: "15/10 67%", "1", "0", "1/0 0%"
    Returns the total/first number only.
    """
    # Escape special chars in stat name
    escaped = re.escape(stat_name)
    # Match the stat name followed by the match total value
    pattern = rf'{escaped}\s+([\d/]+(?:\s+\d+%)?)'
    match = re.search(pattern, text)
    if match:
        val = match.group(1).strip()
        # Extract just the numerator from "15/10" or just "1"
        num_match = re.match(r'(\d+)', val)
        if num_match:
            return int(num_match.group(1))
    return 0


def parse_player_page(text):
    """Parse all relevant stats from a single player page."""
    name = parse_player_name(text)
    match_info = parse_match_info(text)

    if not name:
        return None

    stats = {
        'player': name,
        **match_info,

        # Attacking / PEAK metrics
        'goals':              parse_stat_value(text, 'Shots / on target'),  # we'll use goals from team data
        'shots':              parse_stat_value(text, 'Shots / on target'),
        'shots_on_target':    0,  # parsed from "X/Y" below
        'key_passes':         parse_stat_value(text, 'Key passes / accurate'),
        'dribbles':           parse_stat_value(text, 'Dribbles / successful'),

        # Defensive / ASET metrics
        'duels_won':          0,  # parsed from "X/Y" below
        'defensive_duels_won':0,
        'interceptions':      parse_stat_value(text, 'Interceptions'),
        'clearances':         parse_stat_value(text, 'Clearances'),
        'sliding_tackles':    parse_stat_value(text, 'Sliding tackles'),

        # Passing
        'passes':             0,
        'passes_accurate':    0,
        'pass_accuracy_pct':  0,
        'progressive_passes': parse_stat_value(text, 'Progressive passes / accurate'),
    }

    # Parse fractional stats: "X/Y pct%"
    def parse_fraction(stat_name):
        escaped = re.escape(stat_name)
        pattern = rf'{escaped}\s+(\d+)/(\d+)'
        m = re.search(pattern, text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return 0, 0

    shots_total, shots_on = parse_fraction('Shots / on target')
    stats['shots'] = shots_total
    stats['shots_on_target'] = shots_on

    duels_total, duels_won = parse_fraction('Duels / won')
    stats['duels_total'] = duels_total
    stats['duels_won'] = duels_won

    def_duels, def_won = parse_fraction('Defensive duels / won')
    stats['defensive_duels_won'] = def_won

    passes_total, passes_acc = parse_fraction('Passes / accurate')
    stats['passes'] = passes_total
    stats['passes_accurate'] = passes_acc
    if passes_total > 0:
        stats['pass_accuracy_pct'] = round(passes_acc / passes_total * 100, 1)

    return stats


def score_coug_table(stats):
    """
    Apply COUG Table scoring weights to player stats.

    ASET (Defensive) — automated from Wyscout:
    - Possession Regain (interception/tackle) = 1.0 pt each
    - Clearance from Danger = 1.0 pt each
    - Defensive duel won = 0.5 pt each

    PEAK (Offensive) — automated from Wyscout:
    - Goal = 3.0 pts (injected from team data)
    - Assist = 2.0 pts (injected from team data)
    - Shot on target = 0.5 pts
    - Key pass = 0.5 pts
    - Successful dribble = 0.2 pts

    SET PIECE — requires Spiideo tagging (placeholder)
    """
    aset = (
        stats.get('interceptions', 0) * 1.0 +
        stats.get('clearances', 0) * 1.0 +
        stats.get('sliding_tackles', 0) * 1.0 +
        stats.get('defensive_duels_won', 0) * 0.5
    )

    peak = (
        stats.get('goals', 0) * 3.0 +
        stats.get('assists', 0) * 2.0 +
        stats.get('shots_on_target', 0) * 0.5 +
        stats.get('key_passes', 0) * 0.5 +
        stats.get('dribbles', 0) * 0.2
    )

    set_piece = 0.0  # Spiideo tagged events — placeholder

    total = aset + peak + set_piece

    return {
        'aset_score': round(aset, 2),
        'peak_score': round(peak, 2),
        'set_score':  round(set_piece, 2),
        'total_score': round(total, 2)
    }


def parse_match_pdf(pdf_path):
    """Parse all player pages from a single match PDF."""
    result = subprocess.run(
        ['pdfinfo', pdf_path],
        capture_output=True, text=True
    )
    pages_match = re.search(r'Pages:\s+(\d+)', result.stdout)
    n_pages = int(pages_match.group(1)) if pages_match else 20

    all_players = []

    for page in range(1, n_pages + 1):
        text = extract_page_text(pdf_path, page)
        if 'P L AY E R I N M AT C H' not in text and 'G O A L K E E P E R' not in text:
            continue

        stats = parse_player_page(text)
        if stats and stats.get('player'):
            scores = score_coug_table(stats)
            all_players.append({**stats, **scores})

    return pd.DataFrame(all_players)


def build_season_coug_table(pdf_dir):
    """Process all match PDFs in a directory and build season totals."""
    pdf_dir = Path(pdf_dir)
    all_matches = []

    for pdf_file in sorted(pdf_dir.glob('*.pdf')):
        print(f"Processing: {pdf_file.name}")
        df = parse_match_pdf(str(pdf_file))
        if not df.empty:
            df['source_file'] = pdf_file.name
            all_matches.append(df)

    if not all_matches:
        print("No match PDFs found.")
        return pd.DataFrame()

    season_df = pd.concat(all_matches, ignore_index=True)

    # Season totals per player
    season_totals = season_df.groupby('player').agg(
        matches=('player', 'count'),
        goals=('goals', 'sum'),
        shots_on_target=('shots_on_target', 'sum'),
        interceptions=('interceptions', 'sum'),
        clearances=('clearances', 'sum'),
        duels_won=('duels_won', 'sum'),
        aset_score=('aset_score', 'sum'),
        peak_score=('peak_score', 'sum'),
        set_score=('set_score', 'sum'),
        total_score=('total_score', 'sum'),
    ).round(2).sort_values('total_score', ascending=False).reset_index()

    return season_df, season_totals


if __name__ == '__main__':
    import sys

    # Single match mode
    pdf_path = PLAYER_INGEST_DIR + 'players_2025_11_02_UNCW.pdf'
    print(f"\nParsing: {pdf_path}")
    print("=" * 60)

    df = parse_match_pdf(pdf_path)

    if df.empty:
        print("No player data extracted.")
        sys.exit(1)

    print(f"\n{len(df)} players parsed\n")

    # Show COUG Table for this match
    print("COUG TABLE — CofC vs UNCW (02.11.2025)")
    print("=" * 60)
    display_cols = ['player', 'goals', 'shots_on_target', 'interceptions',
                    'clearances', 'duels_won', 'aset_score', 'peak_score', 'total_score']
    available = [c for c in display_cols if c in df.columns]
    print(df[available].sort_values('total_score', ascending=False).to_string(index=False))

    # Save
    df.to_csv(COUG_TABLE_DIR + '/coug_table_UNCW_match.csv', index=False)
    print("\n✅ Saved to outputs/coug_table_coug_table_UNCW_match.csv")
