# Changelog

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
