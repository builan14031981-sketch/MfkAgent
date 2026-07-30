@echo off
chcp 65001 >nul
echo Starting MfkAgent Desktop...

echo.
echo [1/3] Starting Backend (port 8001)...
start "MfkAgent Backend" cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 127.0.0.1 --port 8001"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Frontend (port 3000)...
start "MfkAgent Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo Waiting for frontend at http://localhost:3000 ...
powershell -Command "$max=60; for($i=0; $i -lt $max; $i++) { try { $r=Invoke-WebRequest -Uri http://localhost:3000 -TimeoutSec 2 -UseBasicParsing; if($r.StatusCode -eq 200){ Write-Host 'Frontend ready!'; exit 0 }} catch { Write-Host ('Waiting... (' + ($i+1) + '/' + $max + ')'); Start-Sleep 1 } }; Write-Host 'TIMEOUT: Frontend did not start within 60s'; exit 1"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Frontend failed to start. Aborting.
  pause
  exit /b 1
)

echo [3/3] Starting Electron...
start "MfkAgent Electron" cmd /c "cd /d %~dp0frontend && set ELECTRON_DEV=true && npx electron ."

echo.
echo MfkAgent Desktop started!
echo.
pause
