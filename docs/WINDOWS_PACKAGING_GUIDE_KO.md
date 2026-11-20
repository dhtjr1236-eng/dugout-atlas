# Dugout Atlas v1.7 — Windows 패키징 준비 상태

## 현재 범위

2026-10-03 유지보수 검토에서 기존 소스 실행의 데이터·설정 위치와 폴더 변경 기능을 복원했다. 현재 앱 버전은 v1.7이다. **소스와 frozen 실행의 저장 정책 통일은 아직 완료되지 않았으며, 이 준비안을 배포 완료본으로 사용하지 않는다.** 목표는 Windows 11이다. v1.7은 소스 배포이며 EXE·installer·GitHub Release는 만들지 않았다.

## 지금 사용하는 방법

기존 `install.bat`, `run.bat`, `python main.py`를 사용한다. `config/paths.py`는 직접 실행하는 파일이 아니다. 함께 변경된 코드가 읽어 사용하는 모듈이다. 이 파일 하나만 복사하면 전체 준비안이 적용되지 않는다.

소스 실행은 v1.61과 동일하게:

- 기존 QSettings 저장소에서 언어·글자 크기·갱신 간격·테마 등을 읽고 저장한다.
- 저장된 data_root가 있으면 그 경로를 사용한다. 없으면 프로젝트 루트를 사용한다.
- DB·즐겨찾기·선수명 캐시·bref 자료는 `<기존 루트>/data/`, 일반 캐시는 `<기존 루트>/cache/`, 로그는 `<기존 루트>/logs/dugout_atlas.log`를 사용한다.
- Settings의 폴더 선택 기능이 동작한다. 사용자가 명시적으로 선택하고 저장하면 빈 대상 폴더에 기존 방식으로 DB 등을 복사하고 재시작부터 적용한다. 원본은 보존한다. 자동 이관은 하지 않는다.

번역·QSS·seed·schema.sql은 읽기 전용 resource_path로 찾는다. 개발에서는 저장소 루트, frozen에서는 sys._MEIPASS를 사용한다.

새로 추가된 선택적 선수명 override와 export 기본 위치는 다음 경로를 사용한다.

```text
%LOCALAPPDATA%\Dugout Atlas\
├─ config\player_names_override.json  (선택)
└─ exports\
```

LOCALAPPDATA가 없거나 상대 경로이면 Path.home()/AppData/Local/Dugout Atlas를 사용한다. export 대화상자에서 사용자가 다른 저장 위치를 선택할 수 있다.

## 선수명 수정

UTF-8 JSON 예:

```json
{"players": [{"en": "Shohei Ohtani", "ko": "오타니 쇼헤이", "ja": "大谷翔平"}]}
```

en은 필수이며 ko/ja는 선택이다. 허용 필드는 이 세 가지이고 값은 비어 있지 않은 문자열이다. 지정한 언어는 seed·자동 이름 캐시보다 우선한다. 통계 ID 매칭은 바꾸지 않는다. 파일이 없거나 JSON·구조가 잘못되면 기존 이름 로딩으로 돌아간다. 잘못된 파일은 warning을 남긴다. 앱을 재시작하면 적용된다. 기본 seed는 수정할 필요 없다.

## 이전 준비안을 이미 실행했다면

이전 준비안은 LOCALAPPDATA의 database/와 config/preferences.ini를 사용했다. 그곳에 새 데이터가 생겼다면 복원된 소스 실행에서는 자동으로 합치지 않는다. 두 위치를 모두 백업하고 필요한 자료를 비교한다. 기존 프로젝트 data/나 기존 사용자 지정 루트가 다시 기본이 된다. 새 preferences.ini의 설정도 자동으로 가져오지 않는다.

수동 백업·이관은 다음 순서로 한다.

1. 앱을 모두 종료하고 기존 루트와 LOCALAPPDATA/Dugout Atlas를 각각 백업한다.
2. DB 파일과 존재하는 -wal/-shm 파일을 함께 보존한다. 실행 중 DB 파일만 복사하지 않는다.
3. 대상에 기존 파일이 있으면 덮어쓰지 말고 어느 사본을 사용할지 결정한다. SQLite 파일 두 개를 단순 합치지 않는다.
4. 캐시는 files/json/headshots 하위 데이터만 필요에 따라 복사한다. cache/*.py와 database/*.py는 프로그램 코드다.
5. Windows의 기존 QSettings는 일반적으로 HKCU/Software/Dugout Atlas/Dugout Atlas에 있다. 레지스트리를 INI로 이름만 바꿔 넣지 않는다. 설정은 앱에서 재지정할 수 있다.

## PyInstaller 준비 파일

`tools/pyinstaller/DugoutAtlas.spec`가 수집 설정의 기준이다. datas는 --add-data 역할, EXE(exclude_binaries=True)+COLLECT는 --onedir 구성을 한다. config 파일과 schema.sql, 이 가이드를 명시적으로 포함하며 사용자 폴더 전체를 수집하지 않는다. matplotlib/seaborn/pybaseball은 collect_all, PyQt6는 hook 및 QtSvg/QtSvgWidgets/backend_qtagg hidden import를 사용한다.

향후 Windows 11 검증 시 실행할 명령:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
.\tools\build_windows.ps1
```

스크립트는 실제 빌드를 실행한다. 이번 작업에서는 실행하지 않았다. `-Clean`을 지정한 경우에만 저장소 build/dist를 삭제한다. 실패 코드를 반환한다.

예상 출력은 dist/DugoutAtlas/DugoutAtlas.exe와 _internal 아래 config/database/schema.sql/런타임 파일이다. 폴더 전체가 실행에 필요하다.

현재 frozen 경로는 설치 폴더에 쓰지 않도록 LOCALAPPDATA 루트를 사용하지만, 기존 QSettings 유지와 소스 실행 호환성을 우선 복원했으므로 전체 저장 정책은 아직 통일되지 않았다. frozen에서는 폴더 변경을 막는다. 실제 배포 전에 정책·이관·오류 처리 검증이 필요하다.

## 배포 전 남은 작업

- 소스·frozen 경로를 통일하면서 기존 data_root·설정·DB를 보존하는 전환 설계
- 빈 DB로 시작되는 상황을 사용자가 알아볼 수 있는 안내
- Windows 11 표준 사용자, 한글·공백 계정명, 설치 폴더 쓰기 금지 환경 검증
- Qt 플러그인, SVG, 그래프, CJK 폰트, export, headshot fallback 확인
- 의존성 버전·라이선스 및 업그레이드·복구 정책 검토

그 후 Inno Setup으로 onedir 전체를 설치하고, 사용자 데이터를 업그레이드·제거 시 보존하는 정책을 적용한다. installer·서명·Release는 별도 작업이다.

참고: https://pyinstaller.org/en/stable/spec-files.html
