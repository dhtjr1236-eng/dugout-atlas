# Dugout Atlas

Windows 11 + Python 3.12+용 PyQt6 데스크톱 MLB 분석 프로그램입니다. MLB Gameday 스타일의 실시간 경기 상태와 FanGraphs / Baseball Reference / Baseball Savant / Statcast 지표를 한 화면에서 조회하도록 구성되어 있습니다.

> 이 프로젝트는 MLB/FanGraphs/Baseball Reference/Baseball Savant의 공식 데스크톱 클라이언트가 아닙니다. 공개 웹/API 데이터의 구조가 바뀌면 외부 소스 어댑터를 업데이트해야 할 수 있습니다.

## 주요 기능

- 날짜별 MLB 경기 일정, 상태, 실시간 점수
- 30초 자동 새로고침
- 볼/스트라이크/아웃, 주자, 현재 타자/투수, 최근 플레이
- 이닝별 라인스코어(R/H/E 포함)
- 홈/원정 라인업 및 투수, 선수 클릭 이동
- MLB 선수 검색 + 자동완성
- 타자: AVG/OBP/SLG/OPS/HR/RBI/SB, fWAR, bWAR, wRC+, OPS+, ISO, BABIP, BB%, K%, wOBA
- 타자 Statcast: Avg/Max EV, Hard Hit%, Barrel%, Sweet Spot%, xBA/xSLG/xwOBA, Chase%, Whiff%
- 수비: OAA, Fielding Run Value, Arm Value(소스 제공 시)
- 투수: ERA/FIP/xFIP/WHIP/K%/BB%, fWAR/bWAR, xERA/xBA/xSLG/xwOBA, Chase%, Whiff%
- 구종별 Usage%, Avg/Max Velocity, Spin Rate, Run Value, Whiff%
- 타자 차트 5종: EV 분포, Barrel%, Hard Hit%, WAR, wRC+
- 투수 차트 4종: 구종 비율, 구종 Run Value, 구속 추이, 구종 Whiff%
- 정규시즌 순위 / 와일드카드 / 팀 스탯 / 리그 팀 스탯
- 다크모드
- SQLite + JSON/File 캐시: 과거 시즌 30일, 현 시즌 FanGraphs/BRef 결과 1시간, 현 시즌 Savant 수비 15분. 로컬 B-Ref 원본은 새 파일을 가져올 때 즉시 교체됩니다.
- `QThread` + `aiohttp` 기반 비차단 UI
- Baseball-Reference 403 대응: 공식 WAR ZIP/TXT/CSV 로컬 가져오기 + 403/429 circuit breaker

## 프로젝트 구조

```text
mlb_advanced_gameday/
├── main.py
├── ARCHITECTURE.md
├── README.md
├── requirements.txt
├── install.bat
├── run.bat
├── run_debug.bat
├── diagnose_sources.bat
├── diagnose_sources.py
├── open_bref_data.bat
├── controllers/
│   └── app_controller.py
├── ui/
│   ├── main_window.py
│   ├── game_view.py
│   ├── lineup_view.py
│   ├── player_view.py
│   ├── league_view.py
│   └── widgets/
│       ├── metric_grid.py
│       └── svg_logo.py
├── services/
│   ├── base_http.py
│   ├── mlb_api.py
│   ├── fangraphs_service.py
│   ├── bref_service.py
│   ├── bref_local_store.py
│   ├── statcast_service.py
│   ├── player_service.py
│   ├── league_service.py
│   └── dataframe_utils.py
├── database/
│   ├── sqlite_manager.py
│   └── schema.sql
├── cache/
│   ├── json_cache.py
│   └── file_cache.py
├── charts/
│   ├── batter_charts.py
│   └── pitcher_charts.py
├── models/
│   ├── game.py
│   ├── player.py
│   └── standings.py
├── workers/
│   └── qt_worker.py
├── config/
│   ├── settings.py
│   ├── logging_config.py
│   └── dark.qss
└── tests/
    ├── test_mlb_parsing.py
    ├── test_cache_and_db.py
    └── test_statcast_aggregation.py
```

더 자세한 계층/동시성/마이그레이션 설명은 `ARCHITECTURE.md`를 참고하십시오.

---

# Windows 11 설치 및 실행 가이드

## 1. Python 설치

Python 3.12 이상 64-bit를 설치하십시오. python.org 설치 프로그램을 사용할 경우 **Add python.exe to PATH**를 체크하는 것을 권장합니다.

PowerShell 또는 명령 프롬프트에서 확인:

```bat
py -3.12 --version
```

또는:

```bat
python --version
```

## 2. 프로젝트 압축 해제

ZIP을 예를 들어 다음 경로에 해제합니다.

```text
C:\DugoutAtlas\
```

OneDrive 동기화 폴더나 권한이 제한된 `Program Files` 아래보다는 일반 사용자 쓰기 가능 폴더를 권장합니다.

## 3. 자동 설치

`install.bat`을 더블클릭합니다.

이 스크립트는 다음을 수행합니다.

1. `.venv` 가상환경 생성
2. pip/setuptools/wheel 업데이트
3. `requirements.txt` 설치
4. 프로젝트 전체 문법 컴파일
5. pytest 실행

정상 종료 시 `Installation and verification completed successfully.`가 표시됩니다.

## 4. 프로그램 실행

`run.bat`을 더블클릭합니다.

수동 실행:

```bat
cd C:\DugoutAtlas
.venv\Scripts\activate
python main.py
```

디버그 콘솔을 계속 열어두려면 `run_debug.bat`을 사용합니다.

---

# 처음 사용하기

## 오늘 경기

프로그램 실행 시 로컬 PC의 오늘 날짜로 MLB 일정을 가져옵니다. 왼쪽 경기 목록에서 경기를 클릭하면 우측 `Gameday` 탭에 상태가 표시됩니다.

라이브 경기 상태는 30초마다 갱신됩니다. 실시간 MLB 데이터는 SQLite/JSON 캐시에서 읽지 않고 매번 MLB Stats API에 요청합니다.

## 다른 날짜

왼쪽 상단 날짜 선택기를 사용합니다. 선택 날짜의 연도를 선수/순위 화면의 기본 시즌으로도 사용합니다.

## 라인업

`Lineups` 탭에서 홈/원정 batting order와 **그 경기에서 실제 등판한 투수 전원**을 표시합니다. MLB boxscore의 `pitchers` 배열과 play-by-play의 실제 투수 등장 순서를 합쳐 누락을 보완하며, IP/H/R/ER/BB/K 게임 라인도 함께 표시합니다. 경기 중에는 30초 자동 갱신으로 새 구원투수가 추가됩니다. 라인업이 아직 공식 발표되지 않은 경우 타순은 빈 상태로 표시될 수 있습니다.

선수 버튼을 클릭하면 `Player` 탭으로 이동합니다.

## 선수 검색

상단 검색창에 최소 두 글자를 입력합니다.

예:

```text
Judge
```

자동완성에서 `Aaron Judge`를 선택하면 선수 데이터를 가져옵니다.

첫 조회는 FanGraphs/Statcast 전체 시즌 데이터 처리 때문에 수 초 이상 걸릴 수 있습니다. 과거 시즌은 기본 30일, 현 시즌 FanGraphs/BRef **선수 결과 캐시**는 1시간 TTL을 사용합니다. B-Ref 로컬 원본 파일은 import 시 즉시 캐시를 무효화합니다.

---

# 데이터와 캐시

## 실시간 — 무캐시

다음 데이터는 캐시를 사용하지 않습니다.

- 경기 목록/스코어 상태
- live feed
- count/outs/runners
- 현재 타자/투수
- 최근 play
- lineups/boxscore

## 외부 통계 캐시

- 과거 시즌 FanGraphs / Baseball-Reference / Statcast 집계: 기본 30일
- 현 시즌 FanGraphs / Baseball-Reference 선수 집계: 1시간
- 현 시즌 Savant 수비: 15분
- 네트워크로 성공한 Baseball-Reference `war_daily_bat.txt` / `war_daily_pitch.txt`: 프로세스 내 30분 메모리 캐시
- 사용자가 가져온 B-Ref 공식 WAR 파일: `data\bref`에서 즉시 우선 사용, 새 import 시 관련 선수 캐시 자동 삭제
- 팀 로고/일부 JSON 파일: 로컬 파일 캐시

빈 결과나 실패 결과는 정상 통계 캐시로 저장하지 않습니다.

DB 파일:

```text
data\mlb_advanced_gameday.sqlite3
```

로컬 캐시:

```text
cache\json\
cache\files\
data\bref\              # 사용자가 가져온 공식 B-Ref WAR 스냅샷
```

모든 캐시를 완전히 초기화하려면 프로그램을 종료한 뒤 `data\mlb_advanced_gameday.sqlite3`, `cache\json`, `cache\files`를 삭제할 수 있습니다. 다음 실행에서 자동 재생성됩니다.

---

# SQLite 스키마

요청된 테이블이 포함되어 있습니다.

- `players`
- `player_stats`
- `pitch_stats`
- `games`
- `team_cache`

`player_stats`는 `(player_id, source, season, role)` 단위로 데이터를 분리해 FastAPI 전환 시에도 동일 캐시 키를 재사용할 수 있습니다.

---

# 네트워크 / 재시도

`services/base_http.py`의 `aiohttp` 요청은 기본 3회 재시도와 exponential backoff를 사용합니다.

설정값은 `config/settings.py`에서 수정할 수 있습니다.

```python
refresh_seconds = 30
cache_ttl_days = 30
request_timeout_seconds = 20
request_retries = 3
```

---

# 외부 데이터 소스 특성

## MLB Stats API

`statsapi.mlb.com`을 사용합니다. 스케줄, live feed, player profile, standings, team stats의 source of truth로 사용합니다.

## pybaseball

FanGraphs와 Baseball Savant/Statcast 접근에 `pybaseball==2.2.7`을 사용합니다. Baseball-Reference의 `bwar_bat()` / `bwar_pitch()`도 지원 경로이지만, 이 함수들은 B-Ref의 `war_daily_*` URL을 직접 요청하므로 B-Ref가 HTTP 403을 반환하는 환경에서는 동일하게 실패합니다.

1.0.5부터 Baseball-Reference는 **사용자가 브라우저로 받은 공식 WAR 파일을 로컬 import하는 경로를 우선**합니다. pybaseball 또는 원본 사이트의 HTML/CSV 컬럼이 변경되면 특정 지표가 `—`로 표시될 수 있으며, 하나의 외부 소스 실패가 전체 선수 페이지를 중단시키지는 않습니다.

## OPS+

OPS+는 Baseball Reference 성격의 지표이므로 사용된 공식 B-Ref 파일 또는 정상 접근 가능한 B-Ref 페이지에 해당 값이 실제로 있을 때만 채웁니다. 값이 없으면 임의로 wRC+나 다른 지표를 OPS+로 대체하지 않습니다.

## Pitch Run Value

구종 테이블의 Run Value는 Statcast pitch-level `delta_run_exp`를 투수 관점으로 부호 반전해 합산합니다. 따라서 이 앱에서는 **양수가 투수에게 좋은 방향(실점 기대 억제)**입니다.

## OAA / Fielding Run Value / Arm Value

수비 leaderboard의 포지션/자격 요건이나 Baseball Savant 컬럼 구조에 따라 일부 선수(특히 DH/특수 포지션)는 값이 없을 수 있습니다. 없는 값은 추정하지 않고 `—`를 표시합니다.

---

# 테스트

가상환경에서:

```bat
python -m compileall -q .
python -m pytest -q
```

현재 프로젝트에 포함된 테스트는 다음을 검증합니다.

- MLB schedule JSON 파싱
- MLB live feed / lineup 파싱
- JSON 캐시 round trip
- SQLite player cache round trip
- SQLite pitch cache round trip
- Statcast 타자 집계 / chase / whiff 계산

---

# 문제 해결

## `No module named PyQt6`

`install.bat`을 먼저 실행하거나:

```bat
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## `No module named pybaseball`

동일하게 requirements를 설치하십시오.

```bat
python -m pip install pybaseball==2.2.7
```

## 경기 목록이 비어 있음

- 해당 날짜가 MLB 비경기일인지 확인하십시오.
- 인터넷 연결과 방화벽에서 `statsapi.mlb.com` HTTPS 접근이 가능한지 확인하십시오.
- `logs\app.log`를 확인하십시오.

## 선수 페이지에서 일부 값만 `—`

외부 사이트에서 해당 지표를 제공하지 않았거나, 데이터 구조가 변경되었거나, 일시적으로 요청이 실패한 경우입니다. 하단의 `Some sources were unavailable` 메시지와 `logs\app.log`를 확인하십시오.

## pybaseball가 오래된 데이터를 반환함

프로그램의 자체 SQLite/JSON 캐시를 삭제한 뒤 재시도하십시오. 필요하면 pybaseball 자체 캐시도 Python 콘솔에서 비울 수 있습니다.

```python
from pybaseball import cache
cache.purge()
```

## UI가 느림

FanGraphs 및 full-season Statcast 첫 조회는 원본 데이터량이 많습니다. 네트워크 작업은 QThread에서 수행되므로 GUI event loop는 차단하지 않지만, 첫 데이터 수집이 끝날 때까지 해당 선수 화면은 loading 상태로 남습니다.

---

# FastAPI + React로 마이그레이션

이 프로젝트에서 그대로 유지할 부분:

```text
models/
services/
database/
cache/
config/
```

교체할 부분:

```text
ui/                    -> React
controllers/           -> FastAPI routes/application layer
workers/qt_worker.py   -> FastAPI async tasks / threadpool
```

권장 API:

```text
GET /api/games?date=2026-09-10
GET /api/games/{game_pk}
GET /api/players/search?q=Judge
GET /api/players/{player_id}?season=2026
GET /api/standings?season=2026
GET /api/teams/{team_id}/stats?season=2026
```

라이브 업데이트는 React가 30초 폴링하거나 FastAPI WebSocket/SSE를 사용하도록 바꿀 수 있습니다. 다중 사용자 서버에서는 SQLite를 PostgreSQL, 로컬 캐시를 Redis로 교체하는 것이 자연스럽습니다.

---

# 개발 시 주의

- 외부 웹사이트의 robots/이용약관 및 합리적인 요청 빈도를 준수하십시오.
- 데이터 소스 실패를 숨기기 위해 서로 다른 지표를 임의 대체하지 마십시오.
- 라이브 데이터에는 30일 캐시를 적용하지 마십시오.
- UI thread에서 requests/pybaseball 호출을 추가하지 마십시오.
- 새 서비스는 PyQt 타입을 import하지 않도록 유지하십시오. 이것이 FastAPI 마이그레이션의 핵심 경계입니다.

## v1.0.1 external-data reliability fixes

If FanGraphs / Baseball Reference fields were blank in v1.0.0, update to v1.0.1.
The external-data adapters were hardened as follows:

- FanGraphs: current JSON leaderboard API is queried first; pybaseball is a fallback.
- Player identity: MLBAM ID is matched directly when available, then FanGraphs ID, then accent-insensitive player name.
- Baseball Reference: bWAR uses pybaseball first and the public daily WAR file as a direct fallback.
- Failed empty external results are no longer treated as a valid 30-day cache hit.
- Cache source keys were versioned (`fangraphs_v2`, `baseball_reference_v2`) so stale blank v1.0.0 cache rows do not suppress re-fetching.
- Pitcher Velocity chart is now sourced independently from Statcast and shows monthly average velocity for the pitcher's most-used fastball-family pitch (FF/SI/FC).

If an older local cache is still suspected, close the app and delete the `cache/` directory. It will be recreated automatically on next launch.


## 업데이트 1.0.2

1.0.2에서는 WAR/wRC+ 연도별 추이, Baseball Reference bWAR, Statcast Barrel% 로딩을 수정했습니다. 기존 1.0.0/1.0.1 캐시는 새 캐시 namespace로 우회하므로 보통 별도 삭제 없이 재수집됩니다. 그래도 값이 비면 프로그램을 종료한 뒤 `clear_cache.bat`을 실행하고 다시 시작하세요.

## 업데이트 1.0.3 — 출처 정확성 / OAA / 경기 등판 투수

- **OAA**: Baseball Savant `Outs Above Average`의 `Fielder / All Positions / 해당 시즌 / min=1` 원문 CSV만 사용합니다. `Runs Prevented`는 별도 지표이며 OAA로 대체하지 않습니다. 현 시즌 OAA는 15분 캐시이며, Savant 직조회 실패 시 오래된 pybaseball 값을 대신 표시하지 않고 오류를 보여줍니다.
- **bWAR / OPS+ / ERA+ (1.0.3 당시 방식)**: 이 방식은 1.0.4에서 폐기되었습니다. 1.0.4는 아래 `Baseball-Reference 1.0.4 동작 방식`을 사용합니다.
- **FanGraphs**: 현재 시즌 캐시를 1시간으로 줄였지만, FanGraphs가 아직 업데이트하지 않은 값까지 프로그램이 임의 계산해 '실시간 fWAR'로 표시하지는 않습니다. 화면에는 FanGraphs가 실제 공개한 값만 표시합니다.
- **경기 투수**: Lineup 화면의 `Pitchers Used`는 MLB live boxscore의 `teams.away.pitchers` / `teams.home.pitchers` 배열 전체를 순서대로 표시합니다. 선발 이후 구원투수가 등판하면 30초 자동 갱신 때 추가되며 IP/H/R/ER/BB/K도 함께 보입니다.
- **출처 확인**: 선수 페이지 하단 `Data Sources`에서 실제 사용한 Baseball Savant / FanGraphs / Baseball-Reference URL과 fetch 시각을 확인할 수 있습니다.

기존 1.0.2 폴더의 캐시와 혼동하지 않도록 1.0.3은 새 폴더에 압축을 풀어 실행하는 것을 권장합니다. 기존 폴더를 재사용한다면 프로그램 종료 후 `clear_cache.bat`을 실행하세요.

---

# Baseball-Reference 1.0.5 동작 방식

로그에 아래와 같이 표시되면 파서 문제가 아니라 Baseball-Reference가 해당 자동 요청을 거절한 것입니다.

```text
403 Client Error: Forbidden
Baseball-Reference rejected automated access (HTTP 403)
```

Sports Reference는 자동 트래픽을 제한하며 공개 API를 제공하지 않습니다. 따라서 1.0.5는 403을 브라우저 위장이나 우회로 뚫으려고 하지 않습니다.

## 가장 확실한 사용법

프로그램 상단에 두 버튼이 추가되어 있습니다.

```text
B-Ref 다운로드
B-Ref 파일 가져오기
```

1. `B-Ref 다운로드`를 누르면 기본 웹 브라우저에서 Baseball-Reference 공식 데이터 디렉터리를 엽니다.
2. 가장 최근 `war_archive-YYYY-MM-DD.zip`을 다운로드합니다. 또는 공식 `war_daily_bat.txt`, `war_daily_pitch.txt` 파일을 각각 받을 수 있습니다.
3. 프로그램의 `B-Ref 파일 가져오기`를 누르고 ZIP/TXT/CSV를 선택합니다.
4. ZIP이면 내부 WAR batting/pitching 테이블을 자동 판별해 둘 다 가져옵니다. 단일 TXT/CSV면 해당 역할의 데이터만 갱신합니다.
5. 현재 열어 둔 선수 페이지가 있으면 import 직후 자동으로 다시 로딩합니다.

가져온 파일은 다음에 정규화되어 저장됩니다.

```text
data\bref\war_daily_bat.csv
data\bref\war_daily_pitch.csv
data\bref\import_meta.json
```

이후 선수 조회에서는 **로컬 공식 B-Ref 스냅샷을 네트워크보다 우선** 사용합니다. MLBAM ID → B-Ref `player_ID` → 악센트 제거 이름 순서로 선수를 매칭하며, bWAR는 B-Ref WAR 파일의 `WAR`을 그대로 사용합니다. FanGraphs WAR를 bWAR로 바꾸어 표시하지 않습니다.

## 403 circuit breaker

로컬 B-Ref 파일이 없을 때만 프로그램이 B-Ref Daily WAR URL을 한 번 시도합니다. 이 요청에서 HTTP 403 또는 429가 확인되면 같은 프로세스에서 B-Ref 네트워크 경로를 24시간 차단합니다.

따라서 이전 버전처럼:

```text
war_daily_bat.txt 실패
→ pybaseball가 같은 URL 다시 요청
→ 선수 페이지 다시 요청
→ 또 403
```

하는 연쇄 실패를 하지 않습니다. `pybaseball.bwar_bat()` / `bwar_pitch()`가 같은 B-Ref URL을 사용하는 구조이므로 403 이후에는 pybaseball B-Ref fallback도 실행하지 않습니다.

## bWAR와 OPS+/ERA+

공식 WAR 파일에 `WAR`이 있으면 bWAR를 표시합니다. WAR 파일에 `OPS_plus` 또는 `ERA_plus`가 포함되어 있으면 OPS+/ERA+도 표시합니다. 하지만 파일에 해당 + 지표가 없다면 프로그램이 다른 사이트 수치나 자체 계산으로 채우지 않고 `—`로 남깁니다. 이 경우 Data Sources 상태는 `PARTIAL`일 수 있습니다.

이 원칙은 숫자를 억지로 채우는 것보다 출처 정확성을 우선하기 위한 것입니다.

## Baseball-Reference 진단

`diagnose_sources.bat`은 기존 SQLite 선수 캐시를 사용하지 않고 현재 로컬 B-Ref 스냅샷과 네트워크 상태를 검사합니다.

기본 실행:

```bat
diagnose_sources.bat
```

명령줄:

```bat
.venv\Scripts\python.exe diagnose_sources.py --player-id 592450 --season 2026 --name "Aaron Judge"
```

투수:

```bat
.venv\Scripts\python.exe diagnose_sources.py --player-id PLAYER_ID --season 2026 --name "Player Name" --pitcher
```

파일을 CLI에서 바로 가져오며 검사할 수도 있습니다.

```bat
.venv\Scripts\python.exe diagnose_sources.py --import-file "C:\Users\me\Downloads\war_archive-2026-09-08.zip" --player-id PLAYER_ID --season 2026 --name "Player Name"
```

`_sources`에 `Baseball-Reference official WAR snapshot (...)`이 표시되면 실제 로컬 B-Ref 공식 파일이 사용된 것입니다.

---

# 1.0.5 matplotlib 경고 수정

이전 버전의 차트는 `constrained_layout=True`를 사용하면서 Qt 탭이 아직 0에 가까운 크기일 때 레이아웃 계산을 시도해 다음 경고가 발생할 수 있었습니다.

```text
UserWarning: constrained_layout not applied because axes sizes collapsed to zero
```

1.0.5는 `constrained_layout`을 제거하고 명시적인 subplot margin과 차트 최소 높이를 사용합니다. 이 경고는 통계 데이터 오류와는 무관했지만 로그 노이즈와 일부 환경의 빈 차트 가능성을 줄이기 위해 수정했습니다.
