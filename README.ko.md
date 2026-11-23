# ⚾ Dugout Atlas

MLB 경기와 선수 데이터를 한 화면에서 탐색하는 Windows 데스크톱 앱입니다. 시즌 중에는 경기와 라인업을 확인하고, 비시즌에는 즐겨찾기 선수와 지난 시즌 기록을 비교할 수 있습니다.

**[Windows 다운로드](https://github.com/dhtjr1236-eng/dugout-atlas/releases/download/v1.92/DugoutAtlas-v1.92-Setup.exe)** · [English](README.md) · [사용 가이드](docs/USER_GUIDE.md) · [변경 내역](CHANGELOG.md) · [전체 릴리스](https://github.com/dhtjr1236-eng/dugout-atlas/releases)

[v1.92 릴리스 및 배포 파일](https://github.com/dhtjr1236-eng/dugout-atlas/releases/tag/v1.92)

Windows 10/11 x64 · Python 설치 불필요

## 주요 기능

- **선수 프로필:** MLB 선수 사진, 요약 카드, 타격·투구 지표와 시즌별 추이.
- **Advanced Compare:** 선수 2~4명의 시즌을 각각 선택하고 지표와 백분위를 비교합니다. 비교표를 CSV로 저장할 수 있습니다.
- **Season Race:** 같은 시즌의 선수 A·B와 선택한 C까지 fWAR 또는 OPS 추이로 비교하고 애니메이션을 저장합니다.
- **경기와 라인업:** 경기 일정·점수·주자 상황과 선수별 기록을 확인합니다.
- **오프시즌 홈:** 즐겨찾기 선수를 이름이나 팀으로 검색하고 저장된 시즌 기록을 둘러봅니다. 경기 목록은 접을 수 있습니다.
- **테마와 언어:** 라이트·다크 테마와 Neon 액센트, 한국어·영어·일본어를 지원합니다.

## 설치와 실행

1. 위의 **Windows 다운로드**에서 설치 파일을 내려받습니다.
2. `DugoutAtlas-v1.92-Setup.exe`를 실행하고 설치 마법사의 안내를 따릅니다.
3. 설치를 마친 뒤 Dugout Atlas를 실행합니다.

통계와 경기 정보를 조회하려면 인터넷 연결이 필요합니다. 데이터 제공처의 응답에 따라 일부 기록이나 사진이 표시되지 않을 수 있습니다.
업데이트하기 전에는 앱을 종료해 주세요. 설치형 앱의 사용자 데이터는 사용자 폴더에 보관됩니다.

소스로 실행하려면 릴리스의 `DugoutAtlas-v1.92-source.zip`을 압축 해제한 뒤, Python 3.12 이상이 설치된 Windows에서 `install.bat`, `run.bat` 순서로 실행하세요. 배포 파일은 같은 릴리스의 `DugoutAtlas-v1.92-SHA256SUMS.txt`에서 확인할 수 있습니다.

## 데이터와 출처

Dugout Atlas는 MLB Stats API, FanGraphs, Baseball-Reference, Baseball Savant / Statcast를 사용합니다. 일부 출처가 실패해도 성공한 출처의 데이터는 계속 표시합니다.

저장 위치와 출처 동작은 [사용자 가이드](docs/USER_GUIDE.md)와 [아키텍처 문서](ARCHITECTURE.md)를 참고하세요.

---

MLB, FanGraphs, Baseball-Reference, Baseball Savant의 공식 클라이언트가 아닙니다.
