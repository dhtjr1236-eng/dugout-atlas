@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Run install.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" diagnose_sources.py
set ERR=%ERRORLEVEL%
echo.
if %ERR% EQU 0 (
  echo Baseball-Reference diagnostic completed: OK
) else if %ERR% EQU 2 (
  echo Baseball-Reference diagnostic completed: PARTIAL
) else (
  echo Baseball-Reference diagnostic completed: UNAVAILABLE
)
pause
exit /b %ERR%
