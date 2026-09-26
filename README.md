# BLACKCAPS / Form book

A dense, static player form tracker for GitHub Pages. It needs no API key, backend, build tool or browser side scraping.

## Publish

1. Create a GitHub repository and add these files at its root.
2. In **Settings → Pages**, choose **Deploy from a branch**, `main`, `/ (root)`.
3. In **Actions**, run **Update cricket data** once. The checked in snapshot also displays immediately; the workflow refreshes it daily at 05:17 UTC.
4. If the workflow cannot push, set **Settings → Actions → General → Workflow permissions** to **Read and write permissions**.

The site appears at `https://YOUR-USERNAME.github.io/REPOSITORY/`. A repository named `YOUR-USERNAME.github.io` appears at the root domain.

## Data rules

- **Roster:** current central contracts from NZC's September 2026 Chapman/Fisher update, plus anyone in Cricsheet's New Zealand men's Test, ODI or T20I playing XIs during the rolling prior 24 months. Casual contracts are not automatically included unless a player has appeared for New Zealand in that period. Edit `CONTRACTS` in `scripts/build_data.py` when NZC changes the list.
- **Performances:** all men's matches from Cricsheet's all JSON archive within that period, including covered first class, List A, international and franchise matches. The last 10 batting innings and bowling spells are kept independently. A player who did not bat or bowl will have no entry for that discipline. Super overs are excluded.
- **Scorecards:** Cricsheet match filenames identify the ESPNcricinfo match. Score links use that match ID. Source coverage is incomplete and publication may lag match day; this page does not assert universal coverage.
- **Stat rules:** wides do not count as balls faced; wides and no balls do not count as legal balls bowled; byes, leg byes and penalty extras are not charged to the bowler. Run outs, retirements and other non bowler dismissals are not bowler wickets. A star means the batter was not out. Test and first class innings appear separately.

The archive and player registry are from [Cricsheet](https://cricsheet.org/downloads/). The contract announcement is from [NZC](https://www.nzc.nz/chapman-moves-to-casual-contract-fisher-earns-maiden-central-contract/). The project is independent of NZC.

## Local use

Run `python scripts/build_data.py` to refresh `data/players.json`, then `python -m http.server 8000` and open `http://localhost:8000/`. Use `--archive PATH` to reuse a downloaded `all_json.zip`, and `--date YYYY-MM-DD` to reproduce a historical snapshot.
