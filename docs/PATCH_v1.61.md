# Dugout Atlas v1.61

출시일: 2026-09-30 · Python 3.12+ · Windows 11 / PyQt6

## 변경 사항

- 경기의 현재 타자·투수, 박스스코어, 플레이별 기록, 득점자와 라인업에서 선수 분석으로 이동합니다. 정수 MLBAM ID와 해당 경기 시즌을 사용합니다.
- 동일 선수의 서로 다른 시즌 요청이 겹쳐도 오래된 응답은 현재 화면을 덮어쓰지 않습니다.
- Season Race: 월간·격주·주간·전체 상세 샘플, 시작/종료 월·일 필터를 제공합니다.
- 일정·ID 준비 후 날짜별 조회 전에 SQLite 캐시와 신규 요청량을 계산합니다. 전체 상세 신규 50개 초과 시 최소 예상 대기 시간을 확인합니다.
- 기존 요청 간격 1초, `fangraphs_race_v1` 캐시, 403/429의 60초 쿨다운을 유지합니다.
- 벡터 헬멧과 비동기 MLB 선수 사진을 선택할 수 있습니다. 사진은 원형 32×32 캐시로 보관하며 실패 시 헬멧으로 표시합니다.
- EN/KO/JA 문구와 기존 Light/Dark/Accent Theme를 지원합니다.
- README 제목·배지, 앱·패키지·HTTP User-Agent, 배포 문서와 CI의 현재 버전을 **1.61**로 통일합니다. 과거 버전의 패치노트와 변경 기록은 당시 버전으로 보존합니다.

## 업데이트

[main ZIP](https://github.com/dhtjr1236-eng/dugout-atlas/archive/refs/heads/main.zip)을 내려받아 압축을 풀고 `install.bat` → `run.bat`을 실행합니다.
Git 사용자는 로컬 작업을 보관한 뒤 `git pull --ff-only origin main`으로 업데이트합니다.
기존 v1.6 미리보기용 패치 ZIP은 v1.61에 재적용하지 않습니다.

[상세 사용 가이드](SEASON_RACE_V161_GUIDE_KO.md) · [전체 변경 기록](../CHANGELOG.md)

## 검증

- 기존 133개 + 기능 확장 14개 + 버전 일치 1개: 총 **148개 테스트**.
- Python 문법 컴파일, Git diff 공백 검사 및 소스 해시 갱신.
- Linux Qt offscreen 검증. Windows 실기기와 실제 외부 API 통신은 이번 검증 범위에 포함하지 않았습니다.
- CJK 폰트가 없는 테스트 환경에서는 Matplotlib 글리프 경고가 발생할 수 있습니다.

WAR는 FanGraphs의 실제 누적 범위 응답만 사용하며 결측값을 합산·추정하지 않습니다.
최소 예상 시간은 신규 요청 수 × 1초이며 실제 통신 시간은 추가됩니다.
