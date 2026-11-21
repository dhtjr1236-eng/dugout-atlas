@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Virtual environment is missing. Run install.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python main.py %*
set "dugout_exit_code=%errorlevel%"
if not "%dugout_exit_code%"=="0" (
    echo.
    echo The application exited with an error. Check logs\dugout_atlas.log under your configured data folder.
    pause
)
exit /b %dugout_exit_code%
