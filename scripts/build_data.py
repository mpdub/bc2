#!/usr/bin/env python3
"""Build a compact BLACKCAPS performance index from Cricsheet JSON."""
import argparse
import datetime as dt
import io
import json
import re
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

URL = 'https://cricsheet.org/downloads/all_json.zip'
OUT = Path(__file__).resolve().parents[1] / 'data' / 'players.json'
CONTRACTS = '''Tom Blundell|Michael Bracewell|Devon Conway|Jacob Duffy|Zak Foulkes|Mitch Hay|Matt Henry|Kyle Jamieson|Tom Latham|Daryl Mitchell|Matthew Fisher|Henry Nicholls|Will O'Rourke|Glenn Phillips|Rachin Ravindra|Mitchell Santner|Ben Sears|Nathan Smith|Blair Tickner|Will Young'''.split('|')
ALIASES = {'Matthew Fisher': ['MJ Fisher', 'Matt Fisher'], 'Mitch Hay': ['MR Hay'], 'Will O\'Rourke': ['W O\'Rourke'], 'Zak Foulkes': ['ZJ Foulkes']}
DISPLAY = {
    'MA Abbas': 'Muhammad Abbas', 'FH Allen': 'Finn Allen', 'A Ashok': 'Adithya Ashok',
    'MS Chapman': 'Mark Chapman', 'KDC Clarke': 'Kristian Clarke', 'KD Clarke': 'Katene Clarke',
    'JA Clarkson': 'Josh Clarkson', 'D Cleaver': 'Dane Cleaver', 'LH Ferguson': 'Lockie Ferguson',
    'D Foxcroft': 'Dean Foxcroft', 'BJ Jacobs': 'Bevon Jacobs', 'NF Kelly': 'Nick Kelly',
    'JR Lennox': 'Jayden Lennox', 'BG Lister': 'Ben Lister', 'RA Mariu': 'Rhys Mariu',
    'CE McConchie': 'Cole McConchie', 'AF Milne': 'Adam Milne', 'JDS Neesham': 'Jimmy Neesham',
    'AY Patel': 'Ajaz Patel', 'MD Rae': 'Michael Rae', 'TB Robinson': 'Tim Robinson',
    'TL Seifert': 'Tim Seifert', 'IS Sodhi': 'Ish Sodhi', 'TG Southee': 'Tim Southee',
    'KS Williamson': 'Kane Williamson',
}
NON_BOWLER_WICKETS = {'run out', 'retired hurt', 'retired out', 'obstructing the field', 'handled the ball', 'timed out'}

def norm(s):
    return re.sub(r'[^a-z]', '', s.lower())

def cutoff_months(today, months=24):
    year, month = today.year, today.month - months
    while month <= 0:
        year -= 1
        month += 12
    return dt.date(year, month, min(today.day, __import__('calendar').monthrange(year, month)[1]))

def scorecard(match_id):
    # Cricsheet's filenames use the ESPNcricinfo match identifier.
    return f'https://www.espncricinfo.com/ci/engine/match/{match_id}.html'

def read_matches(archive, today):
    start = cutoff_months(today)
    matches = []
    with zipfile.ZipFile(archive) as z:
        for filename in z.namelist():
            if not filename.endswith('.json') or not re.fullmatch(r'\d+\.json', Path(filename).name):
                continue
            item = json.loads(z.read(filename))
            info = item['info']
            if info.get('gender') != 'male':
                continue
            dates = info.get('dates', [])
            if not dates or not start <= dt.date.fromisoformat(dates[-1]) <= today:
                continue
            matches.append((Path(filename).stem, item))
    return matches

def summarize(match_id, match, selected):
    info = match['info']
    teams = info['teams']
    registry = info.get('registry', {}).get('people', {})
    interested = {name: registry[name] for names in info['players'].values() for name in names if name in registry and registry[name] in selected}
    if not interested:
        return []
    stats = defaultdict(lambda: defaultdict(lambda: {'runs': 0, 'balls': 0, 'fours': 0, 'sixes': 0, 'out': False, 'balls_bowled': 0, 'conceded': 0, 'wickets': 0}))
    for innings_no, innings in enumerate(match.get('innings', [])):
        if innings.get('super_over') or innings.get('forfeited'):
            continue
        for over in innings.get('overs', []):
            for ball in over.get('deliveries', []):
                batter, bowler = ball.get('batter'), ball.get('bowler')
                extras = ball.get('extras', {})
                if batter in interested:
                    st = stats[batter][innings_no]
                    r = ball['runs']['batter']
                    st['runs'] += r
                    st['balls'] += int('wides' not in extras)
                    if not ball['runs'].get('non_boundary'):
                        st['fours'] += int(r == 4)
                        st['sixes'] += int(r == 6)
                if bowler in interested:
                    st = stats[bowler][innings_no]
                    st['balls_bowled'] += int('wides' not in extras and 'noballs' not in extras)
                    st['conceded'] += ball['runs']['batter'] + extras.get('wides', 0) + extras.get('noballs', 0)
                    st['wickets'] += sum(w['kind'] not in NON_BOWLER_WICKETS for w in ball.get('wickets', []))
                for wicket in ball.get('wickets', []):
                    if wicket['player_out'] in interested:
                        stats[wicket['player_out']][innings_no]['out'] = True
    rows = []
    date = info['dates'][-1]
    for team, names in info['players'].items():
        opponent = next((t for t in teams if t != team), '')
        for name in names:
            if name not in interested:
                continue
            pid = interested[name]
            for innings_no, s in stats.get(name, {}).items():
                common = {'date': date, 'match': match_id, 'innings': innings_no + 1, 'team': team, 'opponent': opponent,
                          'event': info.get('event', {}).get('name', ''), 'format': info['match_type'], 'url': scorecard(match_id)}
                if s['balls'] or s['runs'] or s['out']:
                    rows.append((pid, 'batting', {**common, 'runs': s['runs'], 'balls': s['balls'], 'fours': s['fours'], 'sixes': s['sixes'], 'out': s['out']}))
                if s['balls_bowled'] or s['conceded'] or s['wickets']:
                    rows.append((pid, 'bowling', {**common, 'balls': s['balls_bowled'], 'runs': s['conceded'], 'wickets': s['wickets'], 'balls_per_over': info.get('balls_per_over', 6)}))
    return rows

def build(archive, today):
    matches = read_matches(archive, today)
    names_by_id = defaultdict(set)
    international = set()
    for _, match in matches:
        info = match['info']
        reg = info.get('registry', {}).get('people', {})
        for team, names in info['players'].items():
            for name in names:
                if name in reg:
                    names_by_id[reg[name]].add(name)
                    if team == 'New Zealand' and info['match_type'] in {'Test', 'ODI', 'T20'}:
                        international.add(reg[name])
    contract_ids = set()
    for full in CONTRACTS:
        candidates = [pid for pid, names in names_by_id.items() if any(norm(n) == norm(full) or norm(n) in {norm(a) for a in ALIASES.get(full, [])} for n in names)]
        if len(candidates) != 1:
            # Cricsheet often abbreviates given names. A unique surname match among NZ internationals is safe.
            surname = norm(full.split()[-1])
            candidates = [pid for pid in international if any(norm(n).endswith(surname) for n in names_by_id[pid])]
        if len(candidates) == 1:
            contract_ids.add(candidates[0])
        else:
            print(f'Unresolved contract: {full} ({len(candidates)} matches)')
    selected = international | contract_ids
    lookup = {}
    for pid in selected:
        official = next((n for n in CONTRACTS if pid in contract_ids and (any(norm(alias) == norm(name) for alias in [n] + ALIASES.get(n, []) for name in names_by_id[pid]) or any(norm(name).endswith(norm(n.split()[-1])) for name in names_by_id[pid]))), None)
        raw_name = max(names_by_id[pid], key=len)
        lookup[pid] = {'id': pid, 'name': official or DISPLAY.get(raw_name, raw_name), 'contracted': pid in contract_ids, 'international': pid in international, 'batting': [], 'bowling': []}
    for mid, match in matches:
        for pid, kind, row in summarize(mid, match, selected):
            lookup[pid][kind].append(row)
    for p in lookup.values():
        for kind in ('batting', 'bowling'):
            p[kind] = sorted(p[kind], key=lambda r: (r['date'], r['match'], r['innings']), reverse=True)[:10]
    # Retain current contracted players even when absent from the dataset.
    resolved = {p['name'] for p in lookup.values() if p['contracted']}
    for name in CONTRACTS:
        if name not in resolved:
            lookup['contract:' + name] = {'id': 'contract:' + name, 'name': name, 'contracted': True, 'international': False, 'batting': [], 'bowling': []}
    latest_match = max((match['info']['dates'][-1] for _, match in matches), default=None)
    return {'updated': today.isoformat(), 'source_latest': latest_match, 'window_start': cutoff_months(today).isoformat(), 'match_count': len(matches), 'players': sorted(lookup.values(), key=lambda p: p['name'].split()[-1].lower())}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, help='Existing Cricsheet all_json.zip (for offline runs)')
    parser.add_argument('--date', type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date())
    args = parser.parse_args()
    if args.archive:
        archive = args.archive
    else:
        print(f'Downloading {URL}', flush=True)
        req = urllib.request.Request(URL, headers={'User-Agent': 'BlackcapsFormTracker/1.0 (personal GitHub Pages project)'})
        with urllib.request.urlopen(req, timeout=120) as response:
            archive = io.BytesIO(response.read())
    data = build(archive, args.date)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(',', ':')) + '\n')
    print(f"Wrote {len(data['players'])} players from {data['match_count']} matches to {OUT}")

if __name__ == '__main__':
    main()
