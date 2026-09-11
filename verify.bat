@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Virtual environment is missing. Run install.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m compileall -q .
if errorlevel 1 goto :error
python -m pytest -q
if errorlevel 1 goto :error
echo Verification passed.
pause
exit /b 0
:error
echo Verification failed.
pause
exit /b 1
