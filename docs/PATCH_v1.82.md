# Dugout Atlas v1.82 — 통합 컴포넌트와 테마 개선

## 반영 내용

- `ui/components/__init__.py`에서 `StatCard`, `BaseballDiamondWidget`을 공개 export합니다.
- `charts/__init__.py`에서 `ModernSplineChart`를 공개 export합니다.
- `requirements.txt`에 `scipy>=1.11.0`을 선언합니다.
- 선수 화면의 네 요약 카드를 `PlayerBundle` 데이터에 연결하고, WAR / wRC+ 추이를 `ModernSplineChart`로 표시합니다.
- 선수 추이 기간 값은 `yearly`, `monthly`, `daily`를 유지하며 기존 비동기 Signal/controller 흐름을 사용합니다.
- 홈 화면의 경기 점수와 1·2·3루 주자 상태를 선택된 경기 상세에 연결합니다.
- 라이트·다크 테마의 카드, 라벨, 차트, 베이스 다이아몬드 색상을 `theme_tokens.py`와 `theme.qss` 기준으로 통일합니다.

## 검증

- `.venv`에서 관련 회귀 테스트 61개 통과.
- 전체 pytest는 97% 지점까지 실패 없이 실행되었고, 마지막 관련 테스트 파일도 4개 통과했습니다.
- Windows 실환경의 외부 MLB 데이터 호출은 네트워크 상태에 따라 별도 변동될 수 있습니다.

