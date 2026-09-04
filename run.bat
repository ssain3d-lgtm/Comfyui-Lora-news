@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py %*
) else (
  python app.py %*
)
if errorlevel 1 pause
