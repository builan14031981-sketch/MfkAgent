@echo off
chcp 65001 >nul
echo Starting MfkAgent...

echo.
echo [1/2] Starting Backend (port 8001)...
:: 清理占用 8001 端口的旧后端进程,确保加载最新代码
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo Cleaning up stale backend process PID %%a ...
    taskkill /pid %%a /f >nul 2>&1
)
start "MfkAgent Backend" cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 127.0.0.1 --port 8001"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Frontend (port 3000)...
:: 清理占用 3000 端口的旧前端进程，确保加载最新代码
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
  echo Cleaning up stale frontend process PID %%a ...
  taskkill /pid %%a /f >nul 2>&1
)
start "MfkAgent Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo MfkAgent started!
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8001
echo.
echo Close this window to stop.
pause
