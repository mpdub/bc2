#!/usr/bin/env python3
"""Rebuild data/players.json from Cricsheet's ball-by-ball archive.

Who's in: everyone in data/contracts.txt, plus anyone who has played a men's
Test, ODI or T20 international for New Zealand in the last 12 months.

What's kept: each player's last 10 batting innings and last 10 bowling spells,
from any men's match Cricsheet has in the last 24 months.

Run it with no arguments to download the latest archive. Use --archive to
point at a zip you've already downloaded, and --date to rebuild as of a past day.
"""
import argparse
import calendar
import datetime as dt
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'players.json'
CONTRACTS_FILE = ROOT / 'data' / 'contracts.txt'
ARCHIVE_URL = 'https://cricsheet.org/downloads/all_json.zip'

SELECTION_MONTHS = 12   # played for NZ within this long ago
LOOKBACK_MONTHS = 24    # how far back we go to find their last 10 innings
KEEP = 10

INTERNATIONAL_FORMATS = {'Test', 'ODI', 'T20'}
NON_BOWLER_WICKETS = {'run out', 'retired hurt', 'retired out', 'retired not out',
                      'obstructing the field', 'handled the ball', 'timed out'}
NZ_DOMESTIC = re.compile(r'^(Auckland|Canterbury|Central (Districts|Stags)|Northern (Districts|Brave|Knights)|Otago|Wellington)\b')

# Cricsheet names people by initials and surname. These are the names people actually use.
# Anyone missing just shows up with their Cricsheet name until they're added here.
DISPLAY = {
    'MA Abbas': 'Muhammad Abbas', 'FH Allen': 'Finn Allen', 'A Ashok': 'Adithya Ashok',
    'TA Blundell': 'Tom Blundell', 'MG Bracewell': 'Michael Bracewell', 'MS Chapman': 'Mark Chapman',
    'KDC Clarke': 'Kristian Clarke', 'KD Clarke': 'Katene Clarke', 'JA Clarkson': 'Josh Clarkson',
    'D Cleaver': 'Dane Cleaver', 'DP Conway': 'Devon Conway', 'JA Duffy': 'Jacob Duffy',
    'LH Ferguson': 'Lockie Ferguson', 'D Foxcroft': 'Dean Foxcroft', 'MJ Henry': 'Matt Henry',
    'BJ Jacobs': 'Bevon Jacobs', 'KA Jamieson': 'Kyle Jamieson', 'NF Kelly': 'Nick Kelly',
    'TWM Latham': 'Tom Latham', 'JR Lennox': 'Jayden Lennox', 'BG Lister': 'Ben Lister',
    'RA Mariu': 'Rhys Mariu', 'CE McConchie': 'Cole McConchie', 'AF Milne': 'Adam Milne',
    'DJ Mitchell': 'Daryl Mitchell', 'JDS Neesham': 'Jimmy Neesham', 'HM Nicholls': 'Henry Nicholls',
    'AY Patel': 'Ajaz Patel', 'GD Phillips': 'Glenn Phillips', 'MD Rae': 'Michael Rae',
    'R Ravindra': 'Rachin Ravindra', 'TB Robinson': 'Tim Robinson', 'MJ Santner': 'Mitchell Santner',
    'BV Sears': 'Ben Sears', 'TL Seifert': 'Tim Seifert', 'NG Smith': 'Nathan Smith',
    'IS Sodhi': 'Ish Sodhi', 'TG Southee': 'Tim Southee', 'BM Tickner': 'Blair Tickner',
    'KS Williamson': 'Kane Williamson', 'WA Young': 'Will Young',
}


def months_before(day, months):
    year, month = day.year, day.month - months
    while month <= 0:
        year, month = year - 1, month + 12
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def letters(s):
    return re.sub(r'[^a-z]', '', s.lower())


def read_contracts(path=CONTRACTS_FILE):
    contracts, kind = {}, None
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        heading = re.fullmatch(r'\[(\w+)\]', line)
        if heading:
            kind = heading.group(1).lower()
        elif kind:
            contracts[line] = kind
    if not contracts:
        sys.exit(f'No players found in {path}')
    return contracts


def scorecard(match_id):
    # Cricsheet files are named after the ESPNcricinfo match ID.
    return f'https://www.espncricinfo.com/ci/engine/match/{match_id}.html'


def download(url, attempts=4):
    for attempt in range(1, attempts + 1):
        try:
            print(f'Downloading {url}', flush=True)
            req = urllib.request.Request(url, headers={'User-Agent': 'BlackCapsForm/2.0 (github.com/mpdub/bc2)'})
            with urllib.request.urlopen(req, timeout=300) as response:
                return io.BytesIO(response.read())
        except OSError as err:
            if attempt == attempts:
                raise
            print(f'  failed ({err}), trying again in {30 * attempt}s', flush=True)
            time.sleep(30 * attempt)


def wanted_files(z, start):
    """Use the archive's README index to skip matches that are obviously too old or not men's."""
    names = {Path(n).stem: n for n in z.namelist() if re.fullmatch(r'\d+\.json', Path(n).name)}
    readme = next((n for n in z.namelist() if Path(n).name.lower() == 'readme.txt'), None)
    if not readme:
        return list(names.values())
    keep, seen = [], 0
    early = start - dt.timedelta(days=10)  # a Test can start a few days before it finishes
    for line in z.read(readme).decode('utf-8', 'replace').splitlines():
        parts = [p.strip() for p in line.split(' - ')]
        if len(parts) < 5 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', parts[0]) or parts[4] not in names:
            continue
        seen += 1
        if parts[3] == 'male' and dt.date.fromisoformat(parts[0]) >= early:
            keep.append(names[parts[4]])
    # If the index looks broken, don't trust it.
    return keep if seen > len(names) * 0.9 else list(names.values())


def read_matches(archive, today):
    start = months_before(today, LOOKBACK_MONTHS)
    matches = []
    with zipfile.ZipFile(archive) as z:
        for filename in wanted_files(z, start):
            item = json.loads(z.read(filename))
            info = item['info']
            dates = info.get('dates') or []
            if info.get('gender') != 'male' or not dates:
                continue
            if start <= dt.date.fromisoformat(dates[-1]) <= today:
                matches.append((Path(filename).stem, item))
    return matches


def summarise(match_id, match, selected):
    info = match['info']
    registry = info.get('registry', {}).get('people', {})
    ours = {name: registry[name] for names in info['players'].values() for name in names
            if registry.get(name) in selected}
    if not ours:
        return []
    blank = lambda: {'runs': 0, 'balls': 0, 'fours': 0, 'sixes': 0, 'out': False,
                     'faced': False, 'balls_bowled': 0, 'conceded': 0, 'wickets': 0, 'bowled': False}
    stats = defaultdict(lambda: defaultdict(blank))
    for n, innings in enumerate(match.get('innings', [])):
        if innings.get('super_over') or innings.get('forfeited'):
            continue
        for over in innings.get('overs', []):
            for ball in over.get('deliveries', []):
                batter, bowler, extras = ball.get('batter'), ball.get('bowler'), ball.get('extras', {})
                if batter in ours:
                    s = stats[batter][n]
                    runs = ball['runs']['batter']
                    s['faced'] = True
                    s['runs'] += runs
                    s['balls'] += 'wides' not in extras
                    if not ball['runs'].get('non_boundary'):
                        s['fours'] += runs == 4
                        s['sixes'] += runs == 6
                if bowler in ours:
                    s = stats[bowler][n]
                    s['bowled'] = True
                    s['balls_bowled'] += 'wides' not in extras and 'noballs' not in extras
                    s['conceded'] += ball['runs']['batter'] + extras.get('wides', 0) + extras.get('noballs', 0)
                    s['wickets'] += sum(w['kind'] not in NON_BOWLER_WICKETS for w in ball.get('wickets', []))
                for w in ball.get('wickets', []):
                    if w['player_out'] in ours and w['kind'] not in {'retired hurt', 'retired not out'}:
                        stats[w['player_out']][n]['out'] = True
                        stats[w['player_out']][n]['faced'] = True

    rows = []
    teams = info['teams']
    for team, names in info['players'].items():
        opponent = next((t for t in teams if t != team), '')
        for name in names:
            if name not in ours:
                continue
            for n, s in stats.get(name, {}).items():
                common = {'date': info['dates'][-1], 'match': match_id, 'innings': n + 1, 'team': team,
                          'opponent': opponent, 'event': info.get('event', {}).get('name', ''),
                          'format': info['match_type'], 'url': scorecard(match_id)}
                if s['faced']:
                    rows.append((ours[name], 'batting', {**common, 'runs': s['runs'], 'balls': s['balls'],
                                 'fours': s['fours'], 'sixes': s['sixes'], 'out': s['out']}))
                if s['bowled']:
                    rows.append((ours[name], 'bowling', {**common, 'balls': s['balls_bowled'], 'runs': s['conceded'],
                                 'wickets': s['wickets'], 'balls_per_over': info.get('balls_per_over', 6)}))
    return rows


def match_contract(full_name, names_by_id, nz_linked):
    """Find the Cricsheet ID for a contracted player. Prefer exact names, then initial + surname."""
    want = letters(full_name)
    exact = [pid for pid in nz_linked if any(letters(n) == want for n in names_by_id[pid])]
    if len(exact) == 1:
        return exact[0]
    displayed = [pid for pid in nz_linked if any(DISPLAY.get(n) == full_name for n in names_by_id[pid])]
    if len(displayed) == 1:
        return displayed[0]
    first, surname = letters(full_name.split()[0])[:1], letters(full_name.split()[-1])
    pool = [pid for pid in nz_linked if any(
        letters(n.split()[-1]) == surname and n.split()[0][:1].lower() == first for n in names_by_id[pid])]
    return pool[0] if len(pool) == 1 else None


def build(archive, today, contracts):
    matches = read_matches(archive, today)
    selection_start = months_before(today, SELECTION_MONTHS)
    names_by_id = defaultdict(set)
    nz_linked = set()
    last_for_nz = {}
    for _, match in matches:
        info = match['info']
        reg = info.get('registry', {}).get('people', {})
        played = dt.date.fromisoformat(info['dates'][-1])
        for team, names in info['players'].items():
            for name in names:
                pid = reg.get(name)
                if not pid:
                    continue
                names_by_id[pid].add(name)
                if team == 'New Zealand' or NZ_DOMESTIC.match(team):
                    nz_linked.add(pid)
                if (team == 'New Zealand' and info.get('team_type', 'international') == 'international'
                        and info['match_type'] in INTERNATIONAL_FORMATS and played >= selection_start):
                    last_for_nz[pid] = max(last_for_nz.get(pid, ''), info['dates'][-1])

    contract_by_id, missing = {}, []
    for full_name, kind in contracts.items():
        pid = match_contract(full_name, names_by_id, nz_linked)
        if pid:
            contract_by_id[pid] = (full_name, kind)
        else:
            missing.append(full_name)
            print(f"Couldn't find {full_name} in the scorecards. They'll be listed without stats.")

    players = {}
    for pid in set(last_for_nz) | set(contract_by_id):
        raw = max(names_by_id[pid], key=len)
        name, kind = contract_by_id.get(pid, (DISPLAY.get(raw, raw), None))
        if name == raw and re.match(r'^[A-Z]{1,4} ', raw):
            print(f'No full name for {raw}. Add them to DISPLAY in scripts/build_data.py.')
        players[pid] = {'id': pid, 'name': name, 'contract': kind, 'contracted': kind is not None,
                        'international': pid in last_for_nz, 'last_for_nz': last_for_nz.get(pid),
                        'batting': [], 'bowling': []}

    for match_id, match in matches:
        for pid, kind, row in summarise(match_id, match, players):
            players[pid][kind].append(row)
    for p in players.values():
        for kind in ('batting', 'bowling'):
            p[kind] = sorted(p[kind], key=lambda r: (r['date'], r['match'], r['innings']), reverse=True)[:KEEP]

    for full_name in missing:
        pid = 'contract:' + letters(full_name)
        players[pid] = {'id': pid, 'name': full_name, 'contract': contracts[full_name], 'contracted': True,
                        'international': False, 'last_for_nz': None, 'batting': [], 'bowling': []}

    return {
        'updated': today.isoformat(),
        'source_latest': max((m['info']['dates'][-1] for _, m in matches), default=None),
        'window_start': selection_start.isoformat(),
        'lookback_start': months_before(today, LOOKBACK_MONTHS).isoformat(),
        'match_count': len(matches),
        'players': sorted(players.values(), key=lambda p: (p['name'].split()[-1].lower(), p['name'].lower())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--archive', type=Path, help='an all_json.zip you already have')
    parser.add_argument('--date', type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date())
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()

    archive = args.archive or download(ARCHIVE_URL)
    data = build(archive, args.date, read_contracts())

    # Don't overwrite good data with a broken download.
    with_stats = sum(bool(p['batting'] or p['bowling']) for p in data['players'])
    if not args.archive and (data['match_count'] < 500 or with_stats < 15):
        sys.exit(f"Only {data['match_count']} matches and {with_stats} players with stats. Something's off, so leaving the old data alone.")

    args.out.parent.mkdir(exist_ok=True)
    args.out.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{len(data['players'])} players from {data['match_count']} matches. Newest game: {data['source_latest']}.")


if __name__ == '__main__':
    main()
