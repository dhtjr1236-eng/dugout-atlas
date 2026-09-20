# Changelog

## 1.21

- Added local player and team favorites stored in `data/favorites.json`.
- Added game notifications for score and game-status changes involving favorite teams, using the Windows system tray with a status-bar fallback.
- Added Korean tooltips for key Compare metrics such as AVG, OPS, wRC+, fWAR, bWAR, OAA, ERA, FIP, xERA, and Statcast expected metrics.
- Added regression tests for favorites persistence, score/status notification generation, and Compare tooltip coverage.
- Intentionally skipped the previously explored cache/service optimization patch after a Baseball-Reference regression was observed locally. v1.21 does not modify PlayerService, Baseball-Reference data retrieval, FanGraphs/Statcast cache policy, or stale-cache fallback behavior.
- Bumped application/package version to 1.21.

## 1.2

- Improved player autocomplete so surname/middle substring searches such as `Kikuchi` can find `Yusei Kikuchi`.
- Added player-season selection beside the player name.
- Added hitter/pitcher Platoon Splits for AVG/OBP/SLG/OPS/wRC+.
- Added live scoring-play details below the Gameday linescore.

## 1.10.1

- Hardened OAA sourcing so the app reads OAA only from Baseball Savant's official `Outs Above Average` leaderboard using `View: Fielder` with All Positions.
- Removed the historical pybaseball OAA fallback; if the official leaderboard is unavailable, OAA is shown as unavailable instead of using a stale or derived value.
- Preserved the leaderboard's decimal OAA value as a float instead of coercing it to an integer.
- Catchers now also attempt the same official Fielder leaderboard lookup rather than being skipped before the request.
- `Runs Prevented` remains a separate field and can never fill OAA.
- Defense cache namespace bumped to `statcast_defense_v7` so older cached OAA values cannot mask the new source policy.
- Added dedicated regression coverage for exact leaderboard parameters, decimal OAA, no fallback behavior, and catcher lookup.

## 1.10

- Added a new `Compare` tab beside Player for side-by-side player comparisons.
- Compare supports two independent autocomplete searches and displays role-aware MLB/FanGraphs/B-Ref/Statcast metrics for hitter-vs-hitter or pitcher-vs-pitcher comparisons.
- Mixed hitter/pitcher comparisons fall back to a common metric set instead of mislabeling role-specific stats.
- Added pitcher Statcast period selection: Yearly / Monthly / Daily.
- Pitcher Monthly mode uses the latest calendar month in the selected season that contains an actual Statcast appearance; Daily uses the latest actual appearance date, avoiding empty off-day panels.
- Monthly/Daily pitcher Statcast values are aggregated from Baseball Savant pitch-level rows and update the Statcast cards, pitch arsenal, pitch usage, Run Value, Whiff%, and velocity charts together.
- Period data is lazy-loaded off the UI thread and rapid period changes queue the most recent selection.
- Added v1.10 regression coverage for pitcher period slicing and Compare role contracts.

## 1.0.6

- FanGraphs current-season fWAR / wRC+ now use a 5-minute cache and selected players refresh every 5 minutes.
- WAR / wRC+ batter charts now support Yearly / Monthly / Daily period selection.
- Monthly mode uses calendar-month FanGraphs date ranges; Daily mode uses the most recent 14 games.
- Period data is loaded lazily and rapid period changes queue the latest selection correctly.
- FanGraphs cache namespace bumped to `fangraphs_v6`.
- Added v1.0.6 regression coverage and patch notes.

## 1.0.5 — Dugout Atlas 브랜딩 정리

- 앱 제목, 상단 이름, 오류 안내와 설치 메시지를 Dugout Atlas로 통일했습니다.
- 패키지 이름을 `dugout-atlas`로 변경하고 버전은 `1.0.5`로 유지했습니다.
- 앱의 버전 메타데이터와 창 제목에 동일한 버전을 표시합니다.
- README에 사용자가 제공한 이름 변경 전 실제 실행 스크린샷을 추가했습니다.
- 기존 Git 커밋 이력은 보존합니다. 최초 업로드의 v0.1.1 표기는 과거 기록이며 현재 앱 버전이 아닙니다.

## 1.0.5

- Reworked Baseball-Reference handling for real-world HTTP 403/429 environments.
- Added a process-wide B-Ref circuit breaker: after one 403/429, the app stops repeated B-Ref/pybaseball/player-page requests instead of hammering the same blocked domain.
- Added `BRefLocalStore` for user-imported official Baseball-Reference `war_archive-YYYY-MM-DD.zip`, `war_daily_bat.txt`, `war_daily_pitch.txt`, or CSV files.
- Added top-bar `B-Ref 다운로드` and `B-Ref 파일 가져오기` actions; a successful import invalidates B-Ref SQLite cache and reloads the current player.
- Local official B-Ref snapshots are preferred over network access and retain per-role source/import metadata.
- bWAR is never substituted with fWAR; OPS+/ERA+ remain blank when the imported official WAR file does not contain them.
- Updated diagnostics with `--import-file` and local snapshot reporting.
- Removed Matplotlib `constrained_layout` from embedded Qt charts and added minimum canvas sizes to eliminate the collapsed-axes warning.
- Regression suite expanded to 26 passing tests.

## 1.0.4

- Rebuilt Baseball-Reference integration around the official `war_daily_bat.txt` / `war_daily_pitch.txt` datasets with MLBAM-ID matching.
- Added process-wide 30-minute in-memory caching for B-Ref daily WAR files so player clicks do not repeatedly download league-wide data.
- Added exact Baseball-Reference player-page verification using the B-Ref `player_ID`; current-season WAR and OPS+/ERA+ from that page override the daily-file value when available.
- Added a final Baseball-Reference name-search redirect fallback when neither the daily file nor Chadwick can resolve a B-Ref player id.
- Added a 3.25-second global B-Ref request interval, keeping the app below Sports Reference's published 20-requests/minute limit.
- HTTP 429/403 failures are now exposed as source errors instead of silently producing `—`; successful daily-file values remain visible as `PARTIAL` when a player-page request is blocked.
- Baseball-Reference cache namespace bumped to `baseball_reference_v7` so old blank/incorrect cached records cannot suppress the new fetch path.
- Player Data Sources now shows provider status (`OK`, `PARTIAL`, `UNAVAILABLE`).
- Added `diagnose_sources.bat` / `diagnose_sources.py` for an uncached Baseball-Reference connectivity and parsing test.
- Regression suite expanded to 23 passing tests.

## 1.0.3

- OAA now uses the current Baseball Savant Fielder / All Positions leaderboard only; `Runs Prevented` can no longer be substituted for OAA.
- Current-season OAA bypasses pybaseball cached fallback and uses a 15-minute application cache. If Savant cannot be reached, the UI reports a source error instead of showing a stale/wrong OAA.
- Baseball-Reference now prefers the official season Player Standard Batting/Pitching leaderboard for bWAR and OPS+/ERA+ from the same player row; the daily WAR dataset and Player Value leaderboard remain B-Ref-only fallbacks.
- Traded-player B-Ref matching prefers aggregate `2TM`/`3TM` rows before individual team stints.
- Data Sources now expose the exact source URLs/fetch timestamps returned for player metrics.
- Lineup view merges MLB boxscore `pitchers` with play-by-play pitcher appearances, so a partial boxscore array cannot collapse the list to only the starter. IP/H/R/ER/BB/K are shown and 30-second refresh adds relievers.
- Current-season FanGraphs/Baseball-Reference application cache reduced to one hour; Savant defense cache reduced to 15 minutes.
- Regression suite expanded to 20 passing tests.

## 1.0.2

- Fixed FanGraphs multi-season parameter ordering (`season=end`, `season1=start`).
- Added history validation and pybaseball fallback when FanGraphs returns aggregate/incomplete range data.
- Added robust player filtering and season deduplication for WAR/wRC+ history charts.
- Fixed Baseball Reference bWAR lookup with normalized player-name + season fallback when MLBAM IDs are missing/malformed.
- Fixed Barrel% calculation using Baseball Savant's canonical `launch_speed_angle == 6` classification, with legacy `barrel` fallback.
- Bumped FanGraphs, BRef, and batter Statcast cache namespaces to invalidate stale empty/broken cached data.
- Expanded regression suite to 13 passing tests.

## 1.0.1

- Fixed FanGraphs blank metrics when Chadwick `playerid_reverse_lookup` fails.
- Added direct FanGraphs JSON leaderboard API with pybaseball fallback.
- Added MLBAM-first and accent-insensitive player matching.
- Added Baseball Reference daily WAR file fallback for bWAR.
- Prevented empty failed responses from becoming persistent 30-day cache hits.
- Versioned external cache keys to bypass stale blank v1.0.0 cache rows.
- Decoupled pitcher Velocity chart from FanGraphs history.
- Velocity now uses monthly Statcast velocity for the primary FF/SI/FC fastball.
- Added regression tests for all fixes above.
