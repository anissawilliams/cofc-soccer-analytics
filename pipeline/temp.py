
import csv, re, glob

player_re = re.compile(r'\((\d+)\)\s+(.+)')
for path in sorted(glob.glob('pipeline/data/outputs/2025/**/*_players.csv', recursive=True)):
    mismatches = 0
    total = 0
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            total += 1
            m = player_re.match(row.get('raw_code', ''))
            if m and m.group(2).strip().lower() != row['name'].strip().lower():
                mismatches += 1
    status = '✅' if mismatches == 0 else f'❌ {mismatches} mismatches'
    print(f"{status}  {path.split('/')[-1]}  ({total} rows)")
