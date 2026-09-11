<div align="center">

# ⚾ Dugout Atlas

**경기의 흐름과 선수의 가치를 한 화면에서.**

더그아웃 아틀라스 · MLB 경기와 선수 분석을 위한 데스크톱 데이터 지도

Windows 데스크톱에서 MLB 실시간 경기와 세이버메트릭스를 함께 살펴보는 분석 앱입니다.

기존 `MLB Advanced Gameday v1.0.5` 소스를 기반으로 합니다. 앱 내부 표기와 소스 버전은 원본을 유지합니다.

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows_11-0078D4)
![UI](https://img.shields.io/badge/UI-PyQt6-41CD52)
![Source version](https://img.shields.io/badge/Source-v1.0.5-172B4D)

[빠른 시작](#빠른-시작) · [주요 기능](#주요-기능) · [사용자 가이드](docs/USER_GUIDE.md) · [구조](ARCHITECTURE.md) · [변경 기록](CHANGELOG.md)

</div>

---

## 한눈에 보기

| 화면 | 확인할 수 있는 내용 |
| :--- | :--- |
| **Gameday** | 날짜별 일정, 실시간 점수, 볼·스트라이크·아웃, 주자, 현재 타자·투수, 최근 플레이 |
| **Lineups** | 홈·원정 타순, 실제 등판한 투수 전원, 투수별 경기 기록 |
| **Player** | 선수 검색, 기본 기록, WAR·wRC+·예상 성적·타구 품질·수비 지표 |
| **Charts** | 타구 속도, Barrel%, Hard Hit%, WAR·wRC+ 추이, 구종 비율·구속·Run Value·Whiff% |
| **League** | 정규시즌 및 와일드카드 순위, 팀·리그 팀 통계 |

## 빠른 시작

**준비:** Windows 11, Python 3.12 이상, 인터넷 연결.

1. GitHub 저장소 상단의 **Code → Download ZIP**으로 소스를 내려받고 압축을 풉니다.
2. `install.bat`을 더블클릭해 실행 환경과 의존성을 설치합니다.
3. 설치 완료 후 `run.bat`을 더블클릭합니다.
4. 날짜와 경기를 선택하거나 상단 검색창에서 선수를 검색합니다.

설치 스크립트는 가상환경 생성, 의존성 설치, 문법 검사, 포함된 테스트 실행을 수행합니다. 문제가 있으면 [설치·문제 해결 가이드](docs/USER_GUIDE.md)를 참고하세요.

<details>
<summary>명령줄로 실행하기</summary>

프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

</details>

## 주요 기능

- **30초 자동 갱신:** 경기 상황과 라인업을 주기적으로 불러옵니다.
- **통합 선수 분석:** MLB 기본 기록에 FanGraphs, Baseball-Reference, Baseball Savant/Statcast 데이터를 결합합니다.
- **타자·투수별 차트:** 타구 품질과 시즌 추이, 구종 특성을 시각화합니다.
- **다크 테마:** 경기·선수·리그 화면에 일관된 어두운 테마를 적용합니다.
- **백그라운드 데이터 조회:** 외부 데이터를 불러오는 작업을 UI 스레드와 분리합니다.
- **출처 표시:** 선수 화면에서 데이터 출처, 조회 시각과 소스별 상태를 확인할 수 있습니다.

## 데이터 출처와 갱신

| 출처 | 주요 데이터 | 갱신 방식 |
| :--- | :--- | :--- |
| MLB Stats API | 일정·점수·라인업·선수 기본 기록·순위 | 라이브 경기 데이터는 캐시 없이 요청 |
| FanGraphs | fWAR, wRC+, FIP, xFIP 등 | 현 시즌 선수 결과 1시간 캐시 |
| Baseball-Reference | bWAR, 제공되는 경우 OPS+/ERA+ | 사용자가 가져온 공식 WAR 파일 우선 |
| Baseball Savant / Statcast | 타구·구종·예상 성적·수비 지표 | 지표별 정책 적용, 현 시즌 Savant 수비 15분 캐시 |

과거 시즌 외부 통계는 기본 30일 캐시를 사용합니다. 첫 선수 조회는 시즌 데이터량에 따라 시간이 걸릴 수 있습니다. 사이트의 갱신 시점과 외부 요청 상태에 따라 일부 값은 늦게 반영되거나 `—`로 표시될 수 있습니다.

### Baseball-Reference 파일 가져오기

1. 앱 상단 **B-Ref 다운로드**로 공식 데이터 디렉터리를 엽니다.
2. 공식 WAR ZIP 또는 TXT/CSV 파일을 다운로드합니다.
3. **B-Ref 파일 가져오기**로 다운로드한 파일을 선택합니다.

가져온 파일은 로컬에 저장되며 선수 조회에 우선 사용됩니다. 자동 요청에서 HTTP 403/429가 확인되면 반복 요청을 중단합니다. bWAR에는 B-Ref 값을 사용하며, 파일에 OPS+/ERA+가 없으면 해당 지표를 비워 둡니다.

## 프로젝트 구조

```text
.
├── main.py                 # 앱 진입점
├── ui/                     # 경기·선수·라인업·리그 화면
├── controllers/            # 화면 이벤트와 데이터 요청 연결
├── services/               # 외부 데이터 조회·정규화·집계
├── models/                 # 경기·선수·순위 데이터 모델
├── charts/                 # 타자·투수 차트
├── workers/                # 백그라운드 작업
├── database/               # SQLite 저장소와 스키마
├── cache/                  # JSON·파일 캐시
├── config/                 # 설정·로깅·테마
├── tests/                  # 파싱·캐시·집계·외부 소스 회귀 테스트
└── docs/                   # 상세 사용자 가이드와 파일 목록
```

화면과 데이터 서비스를 분리한 구조입니다. 향후 FastAPI + React 전환을 위한 계층 설명은 [ARCHITECTURE.md](ARCHITECTURE.md)에 있습니다.

## 문서와 검증

- [상세 사용자 가이드](docs/USER_GUIDE.md): 설치, 사용법, 캐시, B-Ref 가져오기, 문제 해결
- [아키텍처](ARCHITECTURE.md): 데이터 흐름, 동시성, 계층별 역할
- [변경 기록](CHANGELOG.md): 원본 v1.0.1–v1.0.5 수정 내역
- [원본 ZIP 전체 파일 목록](docs/FILE_LIST.md): 추출한 파일 62개
- [배포 준비 기록](docs/PUBLISHING.md): 원본 버전과 업로드 커밋 메시지 구분

설치 후 테스트를 실행하려면:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

원본 변경 기록에는 v1.0.5 기준 26개 테스트 통과가 기록되어 있습니다. 이는 원본의 기록이며 이번 문서 정리에서 재실행한 결과는 아닙니다.

## 프로젝트 안내

MLB, FanGraphs, Baseball-Reference 또는 Baseball Savant의 공식 클라이언트가 아닙니다. 외부 데이터 구조가 변경되면 연동 코드의 수정이 필요할 수 있습니다. 저장소에 별도 라이선스 파일은 포함되어 있지 않습니다.
