# Dugout Atlas 1.81 beta2 — Pitch Analysis 표현·도움말 개선

기준: d40126c의 v1.8 + 기존 1.81beta 패치. beta2는 표현 개선용 패치명이며 정식 앱 버전은 1.8을 유지한다. main 커밋/push는 하지 않았다.

## 바뀐 사용법

투수 페이지 → 투수 분석 → 불러오기. Profile은 먼저 구종별 box plot을 보여준다. 가운데 선(Md)은 중앙값, 상자는 Q1~Q3의 중앙 50% 구간이다. 그래프 오른쪽에서 중앙값·중앙 50% 구간·mph/rpm 단위를 직접 읽고, 구종 옆의 유효 N을 확인한다. 수염은 기존 P10~P90 값으로 유지한다.

구종 선택 아래 한 줄 요약과 유효 N/전체 N·결측 수·해석 주의 상태를 보여준다. ‘상세 보기’를 누르면 P10/P90·표준편차와 기존 수치를 볼 수 있다. 지표 이름에 마우스를 올리면 짧은 설명을 제공한다.

Matchup은 상황/구종 선택, 한 줄 요약, 표본 수, 사용률/Whiff 막대그래프를 먼저 보여준다. Whiff는 헛스윙 수/스윙 수와 %, 해당 구종 투구 수를 함께 표시한다. 사용률의 분모는 해당 상황에서 구종을 확인한 투구 수이며 Whiff의 분모와 다르다. 스윙 0개는 미계산이다.

표본 부족 여부는 beta1의 기존 small 플래그를 그대로 읽어 ‘해석 주의’로 표현한다. Profile은 지표별 유효 N, Matchup은 상황 투구·스윙·결과 확인 N을 함께 표시한다. 자동 요약은 관측값만 설명하며 좋음/나쁨·원인·부상·최적 투구를 판단하지 않는다.

영어/한국어/일본어 제목·요약·지표 도움말·상태를 제공한다. 기존 translate_widgets의 처리 후 새 분석 위젯의 표현 갱신 훅을 호출해 언어 변경 시 요약과 그래프를 다시 그린다. 기존 번역 데이터 형식과 테마 토큰을 유지한다.

## 계산 보존

services/pitch_analysis.py, services/statcast_service.py, services/player_service.py, controllers/app_controller.py는 beta1과 바이트 단위로 동일하다. 결과 payload를 수정하지 않으며 중앙값·사분위수·SD·백분위수·사용률·Whiff를 재계산하지 않는다. 기존 PlayerView 변경은 beta2 표시명뿐이다. Change는 추가하지 않았다. DB migration·새 다운로드·새 의존성은 없다.

이번 표현 변경 파일: ui/pitch_analysis_view.py, ui/player_view.py(표시명), config/translations.json, config/i18n.py(표현 갱신 훅), tests/test_pitch_analysis_presentation.py, 이 가이드.

## 적용·복구

앱을 종료하고 기존 소스 및 데이터 위치를 백업한다. 이 ZIP은 beta1 기능을 포함한 통합 beta2 payload이므로 v1.8 기준 소스와 기존 1.81beta 적용본에서 사용할 수 있다.

`patch/payload/` 안의 내용을 main.py가 있는 폴더에 복사한다. 폴더를 합치고 같은 파일만 교체한다. 해당 파일을 직접 수정했다면 manifest의 main 기준/beta1 SHA와 비교하고 update.patch를 검토한다. 다른 최신 소스를 무조건 덮어쓰지 않는다.

기존 가상환경에서 compileall·pytest를 실행하고 run.bat으로 시작한다. 복구는 앱 종료 후 백업 소스를 복원하며 DB·캐시·개인 설정을 삭제하지 않는다. beta1로 돌아갈 때는 beta2 UI/번역/i18n 파일을 함께 복원한다.

최종 검증 결과는 ZIP의 VERIFICATION_KO.txt에 있다. 목표는 Windows 11이며 Linux Qt offscreen 검증은 Windows 실환경 검증을 대신하지 않는다. Matplotlib의 CJK 글꼴 및 boxplot API 경고는 실행 환경에 따라 남을 수 있다.
