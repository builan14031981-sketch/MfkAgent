@echo off
chcp 65001 >nul
echo Starting MfkAgent Desktop...

echo.
echo [1/3] Starting Backend (auto-detecting port)...
:: 清理占用 8001 端口的旧后端进程,确保加载最新代码
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo Cleaning up stale backend process PID %%a ...
    taskkill /pid %%a /f >nul 2>&1
)
start "MfkAgent Backend" cmd /c "cd /d %~dp0backend && python main.py"

echo Waiting for backend port file...
set BACKEND_PORT=8001
REM Phase 9 P1: 等待端口文件就绪（最多 10 秒），读取自动检测到的端口
for /L %%i in (1,1,20) do (
    if exist "%~dp0backend\.mfkagent_port" (
        set /p BACKEND_PORT=<"%~dp0backend\.mfkagent_port"
        echo Backend port detected: %BACKEND_PORT%
        goto :port_ready
    )
    timeout /t 1 /nobreak >nul
)
echo WARNING: Port file not found, using default port 8001
:port_ready

echo Waiting for backend at http://127.0.0.1:%BACKEND_PORT% ...
powershell -Command "$port=%BACKEND_PORT%; $max=60; for($i=0; $i -lt $max; $i++) { try { $r=Invoke-WebRequest -Uri http://127.0.0.1:$port/health -TimeoutSec 2 -UseBasicParsing; if($r.StatusCode -eq 200){ Write-Host 'Backend ready!'; exit 0 }} catch { Write-Host ('Waiting... (' + ($i+1) + '/' + $max + ')'); Start-Sleep 1 } }; Write-Host 'TIMEOUT: Backend did not start within 60s'; exit 1"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Backend failed to start. Aborting.
  pause
  exit /b 1
)

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
set ELECTRON_DEV=true
start "MfkAgent Electron" cmd /c "cd /d %~dp0frontend && npx electron ."

echo.
echo MfkAgent Desktop started!
echo.
pause
