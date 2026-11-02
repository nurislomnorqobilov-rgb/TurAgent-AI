@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 scripts\get_video.py
) else (
  python scripts\get_video.py
)
pause
