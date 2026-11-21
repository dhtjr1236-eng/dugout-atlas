# Neon HUD — 1단계

설정의 **액센트 색상 / 스타일 → 네온 HUD**를 선택합니다. 선택값은 기존 QSettings에 저장되며 취소 시 이전 액센트로 복구됩니다. 라이트 모드는 어두운 청록색 숫자를 사용하고 글로우는 끕니다.

- 공통 `HudPanel`: 토큰 기반 배경, 잘린 코너 브래킷과 프레임 표시. 애니메이션 타이머 없음.
- `StatCard`: 공통 패널 상속, Neon에서 32pt KPI·시안 숫자·다크 전용 제한된 글로우·긴 그라데이션 인디케이터.
- `ModernSplineChart`: 사용자가 추가한 글로우 레이어를 다크 Neon에서만 적용.
- 액센트 유효성 검사는 `ACCENT_OVERRIDES`를 기준으로 통일.
- 실시간 테마 전환 시 이미 생성된 HUD 위젯도 스타일을 갱신.

프리뷰는 실제 Qt 위젯과 명시된 예시 데이터를 사용합니다. 실제 선수 기록이나 2단계 선수 화면 재배치 결과가 아닙니다.

```powershell
.\.venv\Scripts\python.exe tools/preview_neon_hud.py --output output/neon-stage1
```

2단계 선수·비교 화면 재구성과 3단계 레이스·영상 내보내기는 별도 승인 후 진행합니다.
