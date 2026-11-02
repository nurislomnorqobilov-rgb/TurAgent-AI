@echo off
cd /d "%~dp0"
echo ============================================================
echo  TURAGENT AI - CLOUDFLARE WORKERS + D1 (LOCAL)
echo ============================================================
where node >nul 2>&1
if errorlevel 1 (echo ERROR: Node.js topilmadi. https://nodejs.org/ dan LTS ni ornating.& pause & exit /b 1)
if not exist "node_modules\wrangler" (
 echo Wrangler kutubxonasi ornatyapti...
 call npm install --no-audit --no-fund
 if errorlevel 1 (echo ERROR: npm install ishlamadi. Internet va npm ni tekshiring.& pause & exit /b 1)
)
if not exist ".dev.vars" copy /y ".dev.vars.example" ".dev.vars" >nul
call npm run db:local
if errorlevel 1 (echo ERROR: D1 lokal migratsiya bajarilmadi.& pause & exit /b 1)
echo.
echo Sayt: http://localhost:8787
call npm run dev
pause
