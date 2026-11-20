# Dugout Atlas 1.92 Windows 설치 파일

## 사용 방법

`DugoutAtlas-v1.92-Setup.exe`를 실행하고 설치 언어(한국어/영어), 설치 폴더,
바탕화면·시작 메뉴 바로가기를 선택합니다. 설치 완료 화면의 실행 항목을
선택하면 Dugout Atlas가 한 번 실행됩니다. 별도 Python 설치는 필요 없습니다.
통계 제공처에서 데이터를 가져올 때 인터넷 연결이 필요합니다.

기본 설치 위치는 `%LOCALAPPDATA%\Programs\Dugout Atlas`이며 관리자 권한을
요구하지 않습니다. Windows x64용입니다. macOS용 빌드는 포함하지 않습니다.
인증서로 서명하지 않은 로컬 빌드이므로 Windows가 게시자를 확인하지 못할 수 있습니다.

프로그램 제거는 Windows 설정의 설치된 앱 목록에서 수행합니다.
설치 프로그램은 사용자 데이터나 QSettings를 삭제하는 명령을 포함하지 않습니다.
설치 중 실행 중인 앱의 종료가 필요하면 Inno Setup의 표준 안내를 사용합니다.

## 데이터 위치와 기존 소스 실행 사용자

설치형 앱은 `%LOCALAPPDATA%\Dugout Atlas` 아래에 `data`, `cache`, `logs`를
저장하고 기존 QSettings 이름을 사용합니다. 기존 소스 실행 폴더의 DB와
캐시는 설치 파일에 포함하거나 자동 복사하지 않습니다. 기존 자료는 원래
위치에 남습니다. 기존 소스 실행에서 사용자 지정 data_root를 지정했어도
현재 frozen 실행은 위 기본 사용자 폴더를 사용합니다.

기존 자료를 옮기려면 양쪽 앱을 종료하고 두 위치를 먼저 백업하세요.
파일이 이미 있는 경우 덮어쓰지 말고 사용할 사본을 정해야 합니다.
실행 중 SQLite DB 하나만 복사하지 말고 WAL/SHM을 포함한 백업을 사용하세요.
업데이트·제거는 사용자 폴더를 보존하지만, 오래된 소스 DB의 자동 이관을 뜻하지 않습니다.

## 개발자 빌드

Windows에서 프로젝트 가상환경과 Inno Setup 6.6 이상이 필요합니다.
Inno Setup은 공식 https://jrsoftware.org/isinfo.php 에서 받을 수 있습니다.
빌드 시 최신 Python 패키지로 일괄 업데이트하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_setup.ps1 -Iscc "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

로컬 컴파일러가 `.build-tools/InnoSetup/ISCC.exe`에 있으면 `-Iscc`를 생략합니다.
기존 `dist/DugoutAtlas`를 덮어쓸 때는 빌드 도구의 확인을 처리하거나 이전
빌드 출력을 별도 위치에 보관합니다. `-Clean`은 생성된 build/dist만 정리하므로
이 폴더에 사용자 파일을 두지 않습니다. 캐시·DB 폴더 전체를 지우지 마세요.

`release` 출력:

- `DugoutAtlas-v1.92-Setup.exe`: 사용자용 설치 파일
- `DugoutAtlas-v1.92-source.zip`: 해당 빌드의 앱 소스, 사용자 DB·캐시 제외
- `SHA256SUMS.txt`: 설치 파일과 소스 ZIP의 SHA-256
- `BUILD-INFO.json`: 빌드 Python·플랫폼과 소스 파일별 해시

앱 EXE와 런타임 폴더는 `dist/DugoutAtlas`에 만들어집니다.
설치 없이 사용할 때는 EXE 하나가 아니라 이 폴더 전체가 필요합니다.
의존성 라이선스와 빌드 환경의 패키지 목록은 `_internal/licenses`에 포함됩니다.
PyQt6의 GPL v3 라이선스도 포함하므로 공개 배포 시 정확한 소스와 함께 제공하세요.

## 검증

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/test_installer.ps1
```

검사는 작업공간의 `output/installer-validation/설치 확인`에 설치하고,
Python이 PATH에 없는 상태에서 frozen 앱의 오프라인 검사를 실행합니다.
SQLite·리소스·라이트/다크 Neon·SciPy 그래프·3인 비교를 확인한 뒤 재설치와
제거가 검사 전용 DB·즐겨찾기를 보존하는지 비교합니다. 실제 사용자가 설치한
같은 AppId의 앱이 있으면 검사 설치로 덮어쓰지 않고 중단합니다.

앱의 `--self-test <절대경로/report.json>`은 검증 전용 옵션입니다.
설정·DB를 report 폴더 아래에 격리하며 실제 통계 API를 요청하지 않습니다.
일반 실행의 라이브 API 품질이나 새 Windows PC의 호환성을 보증하는 검사는 아닙니다.
검증 결과와 로그는 `output/installer-validation`에 저장되며 배포하지 않습니다.

## 설치 마법사 출처

[Windows Setup Shell](https://github.com/MrUmid2oo4/windows-setup-shell)의
MIT 설치 셸을 Dugout Atlas에 맞게 수정했습니다.
정확한 원본 커밋과 변경 범위는 `tools/installer/UPSTREAM.md`에 있습니다.
원본의 기존 앱 자동 제거, 언어 레지스트리 쓰기, 이중 실행 경로는 사용하지 않습니다.
별도 글꼴을 다운로드하지 않고 Windows 글꼴로 빌드 시 아트워크를 그립니다.

설치 EXE는 Git 소스 커밋에 넣지 않고 GitHub Release 첨부 파일로 배포합니다.
각 파일은 2 GiB 미만인지 빌드 후 확인합니다. 이 작업은 로컬 제작·검증이며
GitHub 업로드와 README의 다운로드 버튼 변경은 다음 단계입니다.
