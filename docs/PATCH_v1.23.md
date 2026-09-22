# Dugout Atlas v1.23

## Compare 확장

- Compare가 기본 2명에서 최대 4명까지 지원합니다.
- 타자 Compare의 27번째 지표로 Baseball Savant Sprint Speed를 추가했습니다.
- Compare OAA는 데이터 원본을 바꾸지 않고 화면에서 정수로 표시합니다.

## League Position

타자 비교의 오른쪽 패널에 실제 선택 시즌 리그 분포 기반 League Position을 추가했습니다.

- AVG / wRC+: FanGraphs qualified hitters 분포
- Sprint Speed: Baseball Savant Sprint Speed 리더보드 분포
- OAA: Baseball Savant OAA 리더보드 분포
- percentile은 실제 분포에서 해당 값 이하 선수 비율로 계산합니다.
- 같은 시즌 분포는 프로세스 메모리에 캐시합니다.
- 외부 소스 하나가 실패하면 해당 지표만 비워 두고 Compare 자체는 계속 동작합니다.

## Comparison Insights UI

오른쪽 영역은 가로로 넓은 표 대신 세로 카드/스크롤 중심으로 구성했습니다. League Position과 Head-to-Head를 분리하여 MLB 전체 위치와 현재 선택 선수 사이의 상대 우위를 혼동하지 않도록 했습니다.

Head-to-Head는 타자의 Contact, Power, Discipline, Speed, Defense, Overall 및 투수의 역할별 카테고리를 현재 비교군 안에서 평가합니다. 이 순위는 MLB 전체 percentile이 아닙니다.

## 안정성

기존 Baseball-Reference, FanGraphs 선수 조회, Statcast 선수 데이터 및 캐시 정책은 변경하지 않았습니다. League Position은 별도 서비스에서 필요한 리더보드 분포만 조회하며 UI 스레드 밖에서 실행됩니다.
