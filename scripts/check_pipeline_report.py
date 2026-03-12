import json
from pathlib import Path

report_path = Path('data/pipeline_report.json')
if not report_path.exists():
    print("Report not found.")
    exit(1)

report = json.loads(report_path.read_text())
teams = report['teams']

# Show best and worst match rates
sorted_teams = sorted(teams, key=lambda t: t['found'], reverse=True)

print('TOP 5 (most players found in 2K14):')
for t in sorted_teams[:5]:
    total = t['found'] + t['skipped']
    rate = t['found'] / total if total > 0 else 0
    print(f'  {t["abbr"]}: {t["found"]}/{total} ({rate:.0%})')

print()
print('BOTTOM 5 (fewest players found):')
for t in sorted_teams[-5:]:
    total = t['found'] + t['skipped']
    rate = t['found'] / total if total > 0 else 0
    print(f'  {t["abbr"]}: {t["found"]}/{total} ({rate:.0%})')

print()
total_found = report['players_found']
total_skipped = report['players_skipped']
total_all = total_found + total_skipped
print(f'Total: {total_found} found, {total_skipped} skipped')
match_rate = total_found / total_all if total_all > 0 else 0
print(f'Match rate: {match_rate:.1%}')
