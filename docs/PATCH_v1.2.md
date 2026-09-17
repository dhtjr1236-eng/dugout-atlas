# Dugout Atlas 1.2

## 선수 검색 보강

- 이름 앞부분뿐 아니라 성/이름 중간 문자열도 자동완성에 매칭됩니다.
- 예: `kikuchi` 입력으로 `Yusei Kikuchi`를 찾을 수 있습니다.
- 메인 검색과 Compare의 두 검색창 모두 같은 규칙을 사용합니다.
- MLB 기본 검색이 부분 이름을 놓치면 현재 시즌 MLB 선수 목록을 한 번 캐시해 보완 검색합니다.

## 시즌 선택

- Player 화면의 선수 이름 오른쪽에 시즌 선택 콤보박스를 추가했습니다.
- 현재 시즌 기록이 있으면 현재 시즌을 기본값으로 사용합니다.
- 현재 시즌 기록이 없으면 해당 선수의 가장 최근 MLB 시즌을 기본값으로 사용합니다.
- 시즌 변경 시 Basic / FanGraphs / Baseball-Reference / Statcast / Running / Platoon / 관련 차트를 다시 불러옵니다.

## Platoon Splits

- 타자: Running 아래에 `Platoon Splits` 박스를 표시합니다.
- 투수: Statcast 아래쪽, Pitch Arsenal 위에 표시합니다.
- 타자: vs LHP / vs RHP, 투수: vs LHB / vs RHB.
- AVG / OBP / SLG / OPS / wRC+를 표시합니다.
- FanGraphs split을 우선 사용하고 slash line 누락 시 MLB Stats API의 좌우 split으로 보완합니다.
- 투수 상대 wRC+는 실제 공급 데이터가 있을 때만 표시합니다.

## 라이브 득점 플레이

- Gameday의 Linescore 표 아래에 득점 플레이 표를 추가했습니다.
- 이닝, 타자, 득점 방식, 타점, 실제 득점자, MLB play description을 표시합니다.
- 홈런은 `HR`, 1루타는 `1B`, 2루타는 `2B`, 3루타는 `3B`, 희생플라이는 `SF`, 폭투는 `WP` 등으로 축약해 표시합니다.
- 타점이 없는 폭투/실책성 득점도 실제 득점자 또는 스코어 변화가 확인되면 표시합니다.
- 라이브 피드의 누적 스코어와 runner movement를 함께 사용해 득점 플레이 누락을 줄였습니다.
