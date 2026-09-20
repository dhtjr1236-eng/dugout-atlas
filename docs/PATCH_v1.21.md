# Dugout Atlas v1.21

## 이번 버전의 방향

v1.21은 앞서 검토했던 캐시/서비스 최적화 패치를 포함하지 않습니다.
Baseball-Reference, FanGraphs, Statcast의 기존 데이터 수집 및 캐시 경로는 그대로 유지하고,
사용자 편의 기능만 독립적으로 추가했습니다.

특히 Baseball-Reference의 bWAR 조회 코드와 기존 회귀 테스트 흐름을 변경하지 않습니다.

## 선수 / 팀 즐겨찾기

- 왼쪽 경기 목록 아래에 `즐겨찾기 / 알림` 영역을 추가했습니다.
- 현재 보고 있는 선수를 즐겨찾기에 저장하거나 해제할 수 있습니다.
- 현재 선택한 경기의 원정팀/홈팀을 각각 즐겨찾기에 저장하거나 해제할 수 있습니다.
- 즐겨찾기 선수는 목록에서 더블클릭하면 Player 화면으로 다시 열 수 있습니다.
- 즐겨찾기는 로컬 `data/favorites.json`에 저장되며 Git에는 포함하지 않습니다.

## 경기 알림

- 즐겨찾기 팀이 포함된 경기의 점수 또는 경기 상태가 바뀌면 알림을 표시합니다.
- Windows에서 시스템 트레이 알림을 사용할 수 있으면 네이티브 알림을 사용합니다.
- 시스템 트레이를 사용할 수 없는 환경에서는 앱 상태바 메시지로 폴백합니다.
- 기존 30초 경기 갱신 주기를 그대로 이용하므로 별도의 추가 MLB 폴링을 만들지 않습니다.

## Compare 지표 설명

Compare 표의 주요 지표 셀에 한국어 툴팁을 추가했습니다.

예:
- AVG / OBP / SLG / OPS
- fWAR / bWAR
- wRC+ / OPS+
- OAA
- ERA / FIP / xFIP / xERA
- xBA / xSLG / xwOBA
- Whiff% / Chase%

마우스를 지표 또는 선수 값 위에 올리면 간단한 정의를 볼 수 있습니다.

## 테스트

`tests/test_convenience_features.py`를 추가해 다음을 검증합니다.

- 선수 즐겨찾기 저장/해제
- 팀 즐겨찾기 저장
- 점수 변경 알림 메시지 생성
- 경기 상태 변경 알림 메시지 생성
- Compare 핵심 지표 툴팁 정의

## 의도적으로 제외한 변경

이번 v1.21에는 다음을 포함하지 않습니다.

- PlayerService 캐시 정책 변경
- stale-cache fallback
- Baseball-Reference 데이터 로직 수정
- FanGraphs/Statcast 캐시 정책 변경
- controllers/services 최적화 리팩터링

따라서 v1.2의 외부 데이터 소스 정책과 bWAR 로직은 그대로 유지됩니다.
