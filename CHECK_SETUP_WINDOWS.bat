@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 server\check_setup.py
) else (
 python server\check_setup.py
)
pause
