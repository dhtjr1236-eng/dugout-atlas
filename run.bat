@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Virtual environment is missing. Run install.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
if errorlevel 1 (
    echo.
    echo The application exited with an error. Check logs\app.log.
    pause
)
