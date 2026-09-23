@echo off
setlocal
cd /d "%~dp0"

echo [Dugout Atlas] Creating Python virtual environment...
py -3.12 -m venv .venv 2>nul
if errorlevel 1 (
    echo Python 3.12 launcher not found. Trying default python...
    python -m venv .venv
)
if errorlevel 1 (
    echo Failed to create virtual environment. Install Python 3.12+ from python.org.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

python -m pip install -r requirements.txt -c constraints-release.txt
if errorlevel 1 goto :error

python -m compileall -q .
if errorlevel 1 goto :error

python -m pytest -q
if errorlevel 1 goto :error

echo.
echo Installation and verification completed successfully.
echo Run run.bat to start Dugout Atlas.
pause
exit /b 0

:error
echo.
echo Installation failed. Review the error above and logs\app.log if it exists.
pause
exit /b 1
