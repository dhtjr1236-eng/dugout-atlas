# Dugout Atlas — Architecture

## 1. Architectural goals

The desktop application separates views, controller coordination, data services, and persistence. Existing extension installers also connect behavior at startup; inspect their call sites before changing shared classes.

```text
PyQt6 Views
    │ signals / render models
    ▼
AppController (MVC controller)
    │
    ├── MLBApiService ─────────────── MLB Stats API (LIVE, no read cache)
    ├── PlayerService (facade)
    │     ├── FanGraphsService ───── pybaseball / FanGraphs
    │     ├── BaseballReferenceService ─ B-Ref official WAR / circuit breaker
    │     │      └── BRefLocalStore ─── user-imported official WAR ZIP/TXT/CSV
    │     └── StatcastService ────── pybaseball + Baseball Savant
    └── LeagueService ────────────── MLB Stats API
          │
          ▼
SQLiteManager + JSON/File Cache
```

## 2. MVC boundaries

- **Model**: `models/` dataclasses (`GameSummary`, `GameDetail`, `PlayerProfile`, `PlayerBundle`).
- **View**: `ui/` contains widgets only. It does not perform HTTP or pybaseball calls.
- **Controller**: `controllers/app_controller.py` reacts to Qt signals and dispatches work to background threads.
- **Services**: `services/` contain source-specific adapters and aggregation logic.
- **Persistence**: `database/sqlite_manager.py`, `cache/json_cache.py`, `cache/file_cache.py`.

## 3. Concurrency model

PyQt's GUI thread never performs network or pybaseball work.

- `TaskThread(QThread)` runs each top-level request outside the GUI thread.
- Async MLB calls use `aiohttp` inside the worker thread's event loop.
- Blocking pybaseball calls are further delegated with `asyncio.to_thread` so FanGraphs and Statcast collection can execute concurrently. B-Ref local imports are file I/O in the same worker layer; B-Ref network access is circuit-broken after 403/429.
- `QTimer` triggers live refresh every 30 seconds.
- Late responses for a game that is no longer selected are ignored.

## 4. Caching policy

### Live MLB data

The following are never served from a cache:

- today's schedule / score state
- live game feed
- ball/strike/out state
- bases occupied
- current batter / pitcher
- recent play
- lineup/boxscore state

They are refetched on each refresh.

### Non-live sabermetric data

A 30-day TTL is applied to historical:

- FanGraphs player season metrics
- Baseball Reference player results
- Baseball Savant/Statcast aggregates
- pitch arsenal aggregates
- defense aggregates
- historical chart series
- team logo files

SQLite stores player-level normalized results. JSON/file cache is used for larger or reusable source responses such as Savant fielding leaderboards and team logo files. User-imported official B-Ref WAR snapshots are stored separately under `data/bref/`; importing a new file invalidates B-Ref player-result cache immediately.

## 5. Failure isolation

`PlayerService` intentionally allows partial results. If FanGraphs, Baseball Reference or Savant changes HTML/schema or temporarily blocks a request, MLB profile/basic stats and any other successful sources still render. The player page shows a source-error summary rather than failing the entire view.

## 6. Data-source mapping

### MLB Stats API

- schedule and statuses
- live game feed / play state
- boxscore and lineups
- player profiles
- MLB basic season stats
- standings / wild-card ranks
- team and league/team season stats

### FanGraphs through pybaseball

- fWAR
- wRC+
- FIP / xFIP
- ISO / BABIP / BB% / K% / wOBA
- historical WAR, wRC+, velocity-related columns when available

### Baseball Reference

- bWAR from the official B-Ref daily WAR download files.
- User-imported `war_archive-YYYY-MM-DD.zip`, `war_daily_bat.txt`, `war_daily_pitch.txt`, or CSV snapshots are preferred.
- If no local snapshot exists, one polite direct fetch may be attempted. HTTP 403/429 trips a process-wide circuit breaker so pybaseball/player-page retries do not repeatedly hit the blocked domain.
- OPS+/ERA+ are displayed only when the actual B-Ref data used contains those fields; they are never synthesized from FanGraphs.

### Baseball Savant / Statcast

- exit velocity, barrels, hard-hit, sweet spot
- xBA / xSLG / xwOBA
- chase and whiff calculations from pitch-level data
- pitcher expected stats when available
- OAA / Fielding Run Value / Arm Value
- pitch usage, velocity, spin and run value

## 7. Run Value convention

Pitch-level `delta_run_exp` represents run-expectancy movement from the batting side. The pitcher arsenal table stores `-sum(delta_run_exp)` so positive values indicate runs prevented in this application's pitcher-oriented view. If Baseball Savant changes the source field semantics, update `StatcastService.get_pitch_arsenal()`.

## v1.7 홈 연결

`ui/home_view.py`는 홈 UI와 이동 신호를 담당합니다. `services/home_service.py`가 즐겨찾기와 선택 시즌의 SQLite 캐시 메타데이터를 읽으며 `controllers/app_controller.py`가 worker 실행 및 오래된 응답 제외를 처리합니다. 홈에서 선수 클릭은 MLBAM ID와 시즌을 전달합니다. 기존 화면 탭은 보존하며 새 홈은 마지막 탭으로 추가해 기존 인덱스 의존을 줄입니다.

소스 실행의 데이터 위치와 QSettings는 기존 정책을 유지합니다. 패키지 리소스 경로 도우미와 frozen 준비 코드는 있으나 설치형 배포는 검증 전입니다.
