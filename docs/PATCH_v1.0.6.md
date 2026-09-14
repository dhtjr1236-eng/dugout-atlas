# Dugout Atlas v1.0.6 — FanGraphs live-season & trend periods

## What changed

- Current-season FanGraphs player summaries use a 5-minute cache instead of the previous 1-hour policy.
- While a player page is selected, the controller refreshes the player bundle every 5 minutes so FanGraphs full-season fWAR/wRC+ can advance without reopening the player.
- Batter WAR and wRC+ charts expose **Yearly / Monthly / Daily** period selection.
- Monthly mode uses exact FanGraphs calendar-month date ranges for the selected season.
- Daily mode uses exact FanGraphs single-day date ranges for the most recent 14 games.
- Monthly and Daily data is loaded lazily only when selected.
- Fast period changes are queued so a Monthly → Daily switch cannot leave the newest selection unloaded.
- FanGraphs cache namespace is bumped to `fangraphs_v6`, so stale v1.0.5 rows do not mask this patch.

## Data semantics

The app does not synthesize WAR or wRC+. Full-season, monthly and daily values come from FanGraphs leaderboard responses for the requested season/date range. Daily mode is bounded to the most recent 14 game dates to avoid a full-season request crawl.

## Verification

- `python -m compileall -q .`
- `pytest -q` → **30 passed**
