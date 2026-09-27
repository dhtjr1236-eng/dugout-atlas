# Dugout Atlas v1.5

v1.5는 기존 Compare를 유지하면서 별도 심화 비교 창, 전체 라인업·팀 현지화, 사용자 선택 Accent Theme를 추가한 정식 릴리스입니다.

## 심화 비교

- 메인 창 우측의 **심화 비교 ↗ / Advanced Compare ↗ / 詳細比較 ↗** 버튼에서 별도 창을 엽니다.
- 2–4명의 선수를 각각 자동완성 검색하고 MLBAM ID로 선택합니다.
- 기존 Compare 탭과 메인 화면 동작은 변경하지 않습니다.
- 핵심 MLB/FanGraphs/B-Ref/Savant 지표와 Baseball Savant 기반 백분위를 표시합니다.
- 첫 열은 지표 폭에 맞추고 선수 열은 같은 Stretch 비율을 사용해 2명 비교에서도 좌우 균형을 유지합니다.
- 출처·조건·상태는 표마다 반복하지 않고 하단 **데이터 범위 / 출처 / 상태** 영역에 한 번만 표시합니다.
- 외부 조회는 기존 TaskThread/PlayerService 흐름을 사용해 UI 스레드를 막지 않습니다.

## 다국어와 선수·팀 표시

- 심화 비교 창 전체가 English / 한국어 / 日本語를 지원합니다.
- 기존 24명 KR/JP/TW seed의 검증된 표기는 계속 우선합니다.
- 나머지 실제 라인업 선수는 MLB Korea/MLB Japan locale 선수 페이지를 MLBAM ID 기준으로 best-effort 조회하고 `data/player_name_locales.json`에 캐시합니다.
- MLB locale HTML의 SEO suffix(`Stats, Age, Position, Height, Weight, Fantasy News` 등)는 선수명에서 제거합니다.
- 한국어 이름이 직접 제공되지 않는 외국인 선수는 MLB Japan의 공식 가타카나 표기를 한글 표시로 변환해 영어 fallback을 줄입니다.
- 30개 MLB 팀의 한국어/일본어 전체 이름과 짧은 팀 표기를 일정·Gameday·Lineups·Standings·League stats에 적용합니다.
- 통계 조회와 선수 매칭은 계속 MLBAM ID와 영문 원본명을 사용합니다. 현지화 문자열은 표시 계층에만 사용합니다.

## Accent Theme

기존 Light/Dark 모드를 유지하면서 아래 Accent를 독립적으로 선택할 수 있습니다.

- Classic Blue
- Midnight Gold
- Obsidian Purple
- Magenta White
- Emerald

Accent는 선택 탭, hover/focus, primary button 및 Matplotlib primary series에 반영합니다. success/warning/danger 색은 의미 구분을 위해 고정합니다.

## 데이터 정확성 유지

- OAA: Baseball Savant 공식 OAA
- bWAR: Baseball-Reference 실제 bWAR
- fWAR/wRC+: FanGraphs 원본 값
- 현지화 이름/팀명은 통계 소스 식별키를 변경하지 않음
- 제공처가 반환하지 않은 고급 지표를 다른 값으로 대체하지 않음

## 검증

CI에서 다음 항목을 계속 검증합니다.

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest -q
```

v1.5에는 심화 비교 서비스, locale 이름 정제/캐시, 팀 현지화 및 accent token 회귀 테스트가 추가됩니다.
