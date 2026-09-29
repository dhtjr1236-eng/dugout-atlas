# Dugout Atlas v1.6

기준: main v1.5. 시즌 레이스 v1.5.1, 사용자 이름·창 크기 v1.5.2 변경을 통합한 릴리스입니다.

## 화면

- 메인 창 상단의 밝게/어둡게 버튼을 제거했습니다. 테마는 Settings의 Theme에서 변경합니다.
- 심화 비교 버튼을 기존 Compare 탭의 `+ 선수 추가` 바로 옆으로 옮겼습니다. 클릭하면 같은 심화 비교 창을 엽니다.
- 상단 첫 줄에는 앱 이름·선수 검색·Settings를 두고, 다음 줄에는 B-Ref 다운로드/가져오기·새로고침을 배치했습니다.
- 메인 기본 크기 1296×810, 심화 비교 1350×810. 작은 모니터에서는 작업 영역에 맞게 축소하고 넘치는 내용은 스크롤로 접근합니다.

## 선수 이름

- `config/player_names_seed.json`을 2026-09-29 사용자 첨부 파일의 바이트 내용 그대로 교체했습니다.
- 113명, 그중 사용자 지정 표기 101명. 이전 파일과 달라진 한국어 표기: Randy Arozarena, Teoscar Hernández, Pete Crow-Armstrong, Brandon Nimmo, Max Scherzer, Emmanuel Clase, Edwin Díaz.
- 선수 기록 식별은 기존 MLBAM ID 기준입니다. 이름 표기는 화면·검색 별칭에만 사용합니다.

## 포함된 이전 기능

- 심화 비교의 시즌 레이스, FanGraphs 날짜 범위 fWAR 조회, Preview/Full detail, 재생·슬라이더, 별도 가상 시연 및 현재 화면 PNG/JPEG 저장.
- 상세 사용법과 데이터 제약: `docs/SEASON_RACE_GUIDE_KO.md`.

## 검증

- 전체 133개 테스트 통과, 문법 컴파일 통과.
- Qt offscreen에서 Compare 탭 버튼으로 심화 비교 창이 열리는지 확인. 테마 버튼 제거 후 ThemeManager 설정 전환 확인.
- 첨부 JSON과 저장된 config JSON의 바이트 일치 및 소스 매니페스트 무결성 확인.
- Linux 검증 환경에 CJK 글꼴이 없어 차트 렌더링 경고가 발생했습니다. Windows 11의 실제 글꼴과 화면 크기는 네이티브 사용 환경에서 추가 확인할 수 있습니다.
