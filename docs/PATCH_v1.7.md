# Dugout Atlas v1.7 — 비시즌 홈 및 유지보수

2026-10-06 · Windows 11 대상 Python 소스 업데이트

## 추가 기능

홈 탭에서 시즌을 고르고 로컬 기록 현황·즐겨찾기를 확인합니다. 선수 탐색·선수 비교·리그 순위·Season Race는 기존 화면과 실제로 연결됩니다. 경기 없음, 조회 중, 실패, 로컬 기록 없음 상태를 구분합니다. 좁은 홈 화면은 한 열과 세로 스크롤을 사용합니다. EN/KO/JA, Light/Dark/Accent를 유지합니다.

홈 수치는 전체 MLB 통계가 아닌 로컬 캐시의 선수·소스 키·항목 수입니다. 홈 현황은 worker에서 로컬 자료만 읽습니다. 통계의 결측 WAR를 계산해 채우지 않으며 ID 매칭과 캐시 TTL은 유지합니다.

## 호환성 및 안정성

- 소스 실행에서 기존 QSettings와 data_root/data 구조, 폴더 선택을 유지합니다.
- DB·캐시·설정은 자동 이관·삭제·초기화하지 않습니다.
- 기본 seed 위에 선택적 선수명 override를 적용하고 잘못된 형식은 무시하며 로그로 알립니다.
- 경로 검증, DB 부모 생성, 시작 오류 처리, 로그 등록·중복 방지를 보완합니다.
- 동일 날짜의 자동 일정 갱신은 홈에서 고른 분석 시즌을 초기화하지 않습니다.
- 종료 시 진행 중인 controller 작업을 기다리며 새로운 자동 갱신을 중단합니다.

## 실행 및 업데이트

기존 폴더와 별도 데이터 위치를 백업한 후 현재 main 소스로 업데이트합니다. 기존 가상환경에서는 run.bat, 새 환경에서는 install.bat 후 run.bat을 실행합니다. 기존 유지보수·홈 덮어쓰기 ZIP은 v1.61 표시의 당시 작업본이므로 v1.7 위에 다시 적용하지 않습니다.

[홈 가이드](OFFSEASON_HOME_GUIDE_KO.md) · [사용자 가이드](USER_GUIDE.md) · [패키징 준비 안내](WINDOWS_PACKAGING_GUIDE_KO.md)

## 배포 한계

PyInstaller 스크립트·spec은 준비 파일입니다. 소스/frozen 저장 정책 통일과 실제 Windows 패키징 검증은 완료되지 않았습니다. EXE·installer·GitHub Release·tag를 만들지 않습니다. 기존 패치노트는 당시 버전을 보존합니다.

## 검증

`python -m compileall -q .` 통과. `python -m pytest -q` 기준 **195개 통과**, 실패/오류/skip 0. 기존 Matplotlib CJK 글리프 경고 19개. `git diff --check` 통과. Linux Qt offscreen 검증이며 실제 Windows EXE/installer 검증은 포함하지 않습니다.
