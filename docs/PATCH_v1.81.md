# Dugout Atlas v1.81 — 투수 분석과 Change (2026-10-16)

## 반영 내용

- Pitch Profile: 구종별 구속(mph)·회전수(rpm)의 box plot, 중앙값·중앙 50%·유효 N·결측을 표시합니다. P10/P90·SD는 상세 영역에서 확인합니다.
- Matchup: 타자 손잡이·balls-strikes별 사용률과 Whiff%를 표시합니다. 분자/분모·투구 수를 함께 표시하고 적은 표본은 해석 주의로 안내합니다.
- Change: 같은 투수·구종을 기준일 미만/당일 포함 이후로 분할해 구속·회전수의 중앙값·IQR·유효 N·결측·제외·차이를 비교하고 일별/주별 시계열을 제공합니다.
- Change는 원시 메모리 캐시를 우선 사용합니다. 없으면 자동 조회하지 않으며 사용자가 범위·TTL 안내를 읽고 조회 허용을 체크해야 선택 시즌을 조회합니다.
- 기존 Arsenal·구속 이력과 동일 시즌 원시 데이터를 공유하며 UI에는 집계 결과만 전달합니다. 기존 worker에서 조회·집계하고 오래된 선수·시즌·기준일 응답은 버립니다.
- 첨부한 이미지 기반의 헤더 로고와 EN/KO/JA 도움말·테마 호환을 반영합니다.

## 사용법

선수 페이지에서 투수를 선택하고 **투수 분석**을 엽니다. Profile/Matchup은 불러오기 버튼으로, Change는 시즌·기준일·간격을 선택해 분석합니다. Change의 구종은 조회 후 선택할 수 있습니다. 상세 계산/결측 정책은 [Change 안내](PATCH_1.81beta3_CHANGE_KO.md)를 확인하세요. 해당 문서의 beta 및 미커밋 설명은 정식 통합 전 기록입니다.

## 데이터와 한계

실제 Savant fixture 90구에서 release_speed·release_spin_rate를 확인했습니다. 한 투수·하루의 확인 결과를 모든 시즌에 일반화하지 않습니다. IVB/HB의 실제 필드·단위·방향은 미검증이므로 사용 불가로 표시하며 추정·자동 변환하지 않습니다.

유효 N<30은 화면상의 해석 주의 기준입니다. 관측 차이를 표시하며 원인·피로·부상·최적 폼을 판단하지 않습니다. Change의 같은 길이 전후 기간과 원시 디스크 캐시는 포함하지 않습니다.

DB migration·자동 데이터 이관·설정 초기화 없음. 기존 Statcast TTL(현재 시즌 15분, 과거 30일 설정)과 두 항목 한도의 메모리 raw 재사용을 유지합니다. 앱 종료/퇴출/TTL 만료 후 raw는 없을 수 있습니다. 기존 OPS·GIF/WebP 기능과 install.bat/run.bat을 유지합니다.

## 검증

복원 및 버전 통합 후 compileall과 전체 pytest 결과는 이 문서 하단에 기록합니다. 테스트는 실제 네트워크를 사용하지 않으며 임시 프로필로 설정을 격리합니다. 목표 플랫폼은 Windows 11이고 Linux Qt offscreen 검증은 Windows 실환경 검증을 대신하지 않습니다. EXE·installer·GitHub Release는 생성하지 않습니다.

통합 검증 결과: Python 3.12, `python -m compileall -q .` 성공, `python -m pytest -q -o addopts=''` **281 passed, 38 warnings** (22.64초). `-o addopts=''`는 중복 quiet 옵션만 제거합니다. 경고는 기존 CJK 글리프와 Matplotlib box plot의 vert 인자 사용 중단 예고입니다. Windows 11 실환경 검증은 미실시입니다.
