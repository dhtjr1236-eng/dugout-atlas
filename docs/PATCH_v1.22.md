# Dugout Atlas v1.22 — Light / Dark Theme

## 구현 기준

현재 저장소는 웹 앱이 아니라 **PyQt6 Windows 데스크톱 앱**입니다.
따라서 브라우저의 `localStorage`, `prefers-color-scheme`, `aria-label`을 그대로 사용할 수 없고,
동일한 목적을 PyQt6 네이티브 방식으로 구현했습니다.

- 브라우저 localStorage → `QSettings`
- 저장 키 → `dugout-atlas-theme`
- 시스템 color scheme → `QApplication.styleHints().colorScheme()`
- aria-label → `QPushButton.setAccessibleName()` / `setAccessibleDescription()`
- CSS variables → 역할 기반 Theme Token 사전 + QSS template
- prefers-reduced-motion → Qt가 reduced-motion hint를 노출하는 경우 감지하여 애니메이션 비활성화

## Light / Dark 전환

- 기존 남색 Dark Theme는 그대로 기본 디자인 계열로 유지했습니다.
- 헤더 오른쪽에 `Light` / `Dark` 전환 버튼을 추가했습니다.
- Dark 상태에서는 버튼에 `Light`, Light 상태에서는 `Dark`가 표시됩니다.
- 버튼 클릭 즉시 전환되며 180ms 색상 전환 애니메이션을 적용합니다.
- 저장된 사용자 선택이 있으면 다음 실행에서도 유지됩니다.

## 초기 테마 우선순위

1. `QSettings`의 `dugout-atlas-theme` 값이 `light` 또는 `dark`이면 최우선
2. 저장값이 없으면 운영체제의 Light/Dark 설정 사용
3. 시스템 설정을 판별할 수 없으면 기존 디자인인 Dark 사용
4. 잘못된 저장값은 삭제하고 위 순서로 안전하게 복구

사용자가 버튼으로 테마를 선택하면 명시적 사용자 설정으로 저장되므로 이후 시스템 테마 변경보다 우선합니다.

## 역할 기반 색상 토큰

`config/theme_tokens.py`에 다음 토큰을 정의했습니다.

- `--color-bg`
- `--color-surface`
- `--color-surface-muted`
- `--color-surface-selected`
- `--color-text`
- `--color-text-muted`
- `--color-text-subtle`
- `--color-border`
- `--color-border-strong`
- `--color-primary`
- `--color-primary-hover`
- `--color-primary-soft`
- `--color-success`
- `--color-warning`
- `--color-danger`
- `--shadow-card`

Light Theme 색상은 요청된 권장값을 그대로 사용합니다.

## 적용 범위

새 QSS template은 다음 항목을 Light/Dark 양쪽에서 처리합니다.

- 전체 배경 / 메인 윈도우
- 카드 / GroupBox / 패널
- 검색 input
- 날짜 선택
- Today 및 일반 버튼
- 헤더 테마 토글
- 경기 목록 / 선택 상태
- 즐겨찾기 / 알림 패널
- 상단 탭
- Player / Compare / Standings 표
- Stat 카드 텍스트
- ComboBox / Drop-down
- Scrollbar
- hover / pressed / disabled / focus
- ToolTip / StatusBar

Matplotlib 타자/투수 차트의 배경/텍스트/테두리도 현재 테마 토큰을 사용하도록 변경했습니다.

## 접근성

테마 버튼에는 다음을 적용했습니다.

- 접근 가능한 이름
- 접근 가능한 설명
- tooltip
- 명확한 텍스트 라벨
- 키보드 focus border
- hover / pressed 상태

## 테스트

`tests/test_theme_manager.py`에서 다음을 검증합니다.

- 필수 역할 기반 토큰이 Light/Dark에 모두 존재
- 잘못된 저장 테마 값 제거
- 테마 toggle 후 사용자 설정 저장
- 버튼 라벨 및 접근성 이름 갱신

기존 외부 데이터/경기/선수 로직은 수정하지 않았습니다.
