# Black Caps form

How every Black Cap is going, wherever they're playing. Each player's last ten innings and bowling spells, updated every morning.

Who's on it: everyone with a New Zealand Cricket contract (central or casual), plus anyone who's played a Test, ODI or T20 international for New Zealand in the last 12 months.

## Updating the contracts

NZC announces contract changes in press releases, so the list is kept by hand in `data/contracts.txt`. Edit it on GitHub, one name per line under `[central]` or `[casual]`, and the site rebuilds itself a few minutes later.

## How the daily update works

`.github/workflows/update.yml` runs every morning (NZ time). It downloads [Cricsheet](https://cricsheet.org/downloads/)'s ball-by-ball archive, runs `scripts/build_data.py`, and commits the new `data/players.json`. GitHub Pages then republishes the site.

You can also run it by hand: **Actions → Update scores → Run workflow**. If a run fails, nothing on the site changes; it just keeps the last good data.

If a new player shows up as initials (say "AB Smith"), add their proper name to `DISPLAY` near the top of `scripts/build_data.py`.

## Running it locally

```
python3 scripts/build_data.py
python3 -m http.server 8000
```

Then open http://localhost:8000. Use `--archive all_json.zip` to reuse a download, or `--date 2026-01-31` to rebuild as of a past day.

## Small print

Cricsheet doesn't cover every match (notably New Zealand A games), and new games can take a few days to arrive. Wides don't count as balls faced; byes, leg byes and run outs don't count against the bowler. Super overs are left out.

Not affiliated with New Zealand Cricket.
