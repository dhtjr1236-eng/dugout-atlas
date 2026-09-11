@echo off
setlocal
cd /d "%~dp0"
echo Closing Dugout Atlas before clearing cache is recommended.
if exist cache\json rmdir /s /q cache\json
if exist cache\files rmdir /s /q cache\files
if exist data\mlb_advanced_gameday.sqlite3 del /q data\mlb_advanced_gameday.sqlite3
echo Cache cleared. It will be rebuilt on next launch.
pause
