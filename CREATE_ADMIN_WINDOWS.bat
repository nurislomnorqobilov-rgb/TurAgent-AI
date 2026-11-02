@echo off
setlocal
cd /d "%~dp0"
set "TURAGENT_LOCAL_SQLITE=1"
set "PUBLIC_URL=http://localhost:8000"
set "HOST=127.0.0.1"
set "PORT=8000"
where py >nul 2>&1
if %errorlevel%==0 (
 py -3 server\bootstrap_admin.py
) else (
 python server\bootstrap_admin.py
)
pause
