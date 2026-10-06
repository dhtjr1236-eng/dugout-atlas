## 1.7 유지보수 — 문서·캐시 관리 정리 (2026-10-06)

- 원본 ZIP 파일 목록, 초기 업로드 설명, 수동 소스 체크섬을 제거합니다. 소스 이력은 Git에서 확인합니다.
- README와 사용자 가이드를 현재 사용법 중심으로 정리하고 중복 버전 설명·불필요한 웹 전환 계획을 제거합니다.
- 선수명 수정 안내를 사용자 override 기준으로 통일합니다.
- `clear_cache.bat`의 프로젝트 DB 직접 삭제를 제거하고 설정 화면의 캐시 관리로 안내합니다.
- 앱 버전과 데이터 조회·계산·저장 경로는 변경하지 않습니다.

## 1.7 — 비시즌 홈과 호환성 유지보수 (2026-10-06)

- 홈에서 시즌 선택, 로컬 캐시 현황, 즐겨찾기와 기존 분석 바로가기를 제공합니다.
- 경기 일정 상태를 구분하고 자동 일정 갱신이 선택한 분석 시즌을 덮어쓰지 않도록 합니다.
- 기존 QSettings/data_root를 보존하고 선수명 override, 경로 검증, 시작 오류 및 파일 로그 처리를 보완합니다.
- PyInstaller 준비 파일·가이드를 포함합니다. 설치형 배포는 아직 준비 단계입니다.
- 앱·패키지·HTTP·README·CI·현재 안내문을 v1.7로 통일합니다.
- 상세: [v1.7 패치노트](docs/PATCH_v1.7.md).

## 1.61 — 선수 탐색·시즌 레이스 개선 (2026-09-30)

- 경기의 박스스코어·플레이별 타자/투수·득점자에서 MLBAM ID로 선수 분석에 연결합니다.
- 경기 시즌 전달과 이전 비동기 응답 제외로 다른 시즌의 화면 덮어쓰기를 막습니다.
- 시즌 레이스 월간·격주·주간·전체 상세, 기간 필터와 캐시 기반 요청량 계산을 추가합니다.
- 전체 상세 신규 50개 초과 시 비차단 확인창을 표시합니다.
- 벡터 헬멧, 비동기 MLB 사진 다운로드·원형 캐시와 실패 시 대체 표시를 추가합니다.
- README 제목/배지, 앱·패키지·HTTP 버전, 배포 안내와 CI 검사를 v1.61로 통일합니다.
- 상세: [v1.61 패치노트](docs/PATCH_v1.61.md), [사용 가이드](docs/SEASON_RACE_V161_GUIDE_KO.md).

## 1.6 — 버튼 배치·사용자 선수명 (2026-09-29)

- 테마 버튼은 Settings로 통합, 심화 비교 버튼은 Compare 탭의 선수 추가 옆으로 이동.
- 사용자 첨부 113명 선수명 파일을 그대로 반영.
- 자세한 내용: [v1.6 패치노트](docs/PATCH_v1.6.md).

## 1.5.2 — 사용자 지정 이름과 작은 기본 창 (2026-09-28)

- 101명의 EN/JA/KO 표기를 캐시보다 우선 적용. 기존 목록 포함 113명.
- 메인 1296×810, 심화 비교 1350×810. 작은 화면에서 추가 축소·스크롤 지원.
- [패치노트와 적용 방법](docs/PATCH_v1.5.2.md).

## 1.5.1 — 시즌 레이스 로컬 패치 (2026-09-28)

- 기존 심화 비교에 실제 FanGraphs 범위 fWAR 레이스 탭 확장.
- Preview/Full detail, ID 엄격 매칭, 날짜축·캐시·취소, 재생·슬라이더·효과.
- 실제 기록과 분리한 가상 시연 창, PNG/JPEG 정지 이미지 저장.
- 상세 검증과 제약: [패치노트](docs/PATCH_v1.5.1.md), [가이드](docs/SEASON_RACE_GUIDE_KO.md).
- main commit/push/merge/release 없음.

# Changelog

## 1.5

- Added a separate 2–4 player Advanced Compare window while keeping the existing Compare tab unchanged.
- Balanced two-player and multi-player table columns and consolidated source/condition/status metadata into one footer.
- Added English/Korean/Japanese Advanced Compare UI translation and immediate retranslation after Settings language changes.
- Expanded lineup/player localization beyond the curated KR/JP/TW seed: MLB Korea/MLB Japan locale pages are cached by MLBAM ID; Korean display can fall back to Hangul converted from MLB Japan katakana.
- Added Korean/Japanese names and short labels for all 30 MLB teams across schedules, Gameday, Lineups, Standings and league team stats.
- Stripped MLB locale SEO suffixes such as `Stats, Age, Position...` before caching display names.
- Added persistent accent palettes: Classic Blue, Midnight Gold, Obsidian Purple, Magenta White and Emerald, independent of Light/Dark mode.
- Preserved MLBAM/English identity for FanGraphs, Baseball-Reference, Savant and MLB Stats API matching.
- Details: [v1.5 patch notes](docs/PATCH_v1.5.md).

## 1.41

- Added locale-aware display names and search aliases for 24 curated 2026 KR/JP/TW players.
- Locked Jung Hoo Lee Japanese display to `イ・ジョンフ` and added an idempotence regression test for the duplicated-prefix bug.
- Added Hye-Seong Kim 2026 display-team override `LAD`.
- Corrected Tsung-Che Cheng Korean display to `정쭝저`; the previous spelling remains a search alias.
- Preserved MLBAM/English identity for FanGraphs, Baseball-Reference and Savant matching.
- Details: [v1.41 patch notes](docs/PATCH_v1.41.md).

## 1.40

- Added persistent Settings for game/player refresh intervals, theme, font size and notifications.
- Added English/Korean/Japanese interface and built-in metric explanation translations with immediate switching.
- Added guarded cache cleanup, source-specific invalidation, data-location copying with SQLite backup, and private diagnostics.
- Added settings, localization, source isolation and data-copy regression tests.
- Details: [v1.40 patch notes](docs/PATCH_v1.40.md).

## 1.30

상세 변경·검증 결과: [v1.30 패치 노트](docs/PATCH_v1.30.md)

- Hardened HTTP retries (408/425/429/5xx only), Retry-After, jitter, timeout and bounded streaming responses; reuse sessions across attempts.
- Limited B-Ref archives by total expanded size, entry count and compression ratio; local import metadata now stores basename only.
- Redacted URL query strings, credentials and user home paths from application logs.
- Added source availability states and an explicit refresh control.
- Added CI lint, dependency audit, static security scan and pinned direct release dependencies.
- Updated README and user guide; retained existing FanGraphs/B-Ref/Statcast calculation and player matching logic.

## 1.23

- Compare supports 2–4 players, Sprint Speed and integer OAA display.
- League Position uses FanGraphs/Savant season distributions; Comparison Insights use vertical scrolling cards.
- See `docs/PATCH_v1.23.md` for details.

## 1.22

- Added a Light Theme while preserving the existing navy Dark Theme.
- Added a header-right Light/Dark toggle with accessible name/description, tooltip, keyboard focus styling, hover and pressed states.
- Added role-based theme tokens and a tokenized QSS template for backgrounds, surfaces, text, borders, primary/status colors, controls, tables, tabs, scrollbars, tooltips and status bar.
- Theme selection persists under the `dugout-atlas-theme` key using Qt `QSettings`; invalid values are removed safely.
- When no saved preference exists, the app follows the operating-system Light/Dark color scheme and falls back to Dark when the system value is unavailable.
- Added a 180ms theme color transition and respects a Qt reduced-motion hint when available.
- Batter and pitcher Matplotlib charts now use the active theme tokens and refresh after a theme switch.
- Added theme-manager regression tests.
- No external-data, Baseball-Reference, FanGraphs, Statcast, routing/controller or cache behavior was changed.
- Bumped app/package version to 1.22.

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
