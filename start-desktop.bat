@echo off
chcp 65001 >nul
title MfkAgent Desktop 桌面端启动
echo ========================================
echo   MfkAgent Desktop 桌面端启动
echo ========================================

:: 1. 探测 Python 解释器
set "PYTHON=C:\Users\Asus\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

:: 2. 启动 Backend (port 8001)
echo.
echo [1/3] 启动 Backend 守护进程 (port 8001)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /pid %%a /f >nul 2>&1
)
if exist "%~dp0backend\.mfkagent_port" del "%~dp0backend\.mfkagent_port"
start "Backend Guardian" /min cmd /c "powershell.exe -NoProfile -ExecutionPolicy Bypass -File %~dp0backend_guardian.ps1"

echo   等待 Backend 就绪...
set /a tries=0
:wait_backend_ready
netstat -ano | findstr :8001 | findstr LISTENING >nul
if not errorlevel 1 goto backend_ready
set /a tries+=1
if %tries% geq 30 (
    echo [警告] Backend 启动超时，继续启动前端...
    goto start_frontend_dev
)
ping 127.0.0.1 -n 2 >nul
goto wait_backend_ready

:backend_ready
echo   Backend 已就绪 (http://127.0.0.1:8001)

:: 3. 启动 Frontend Dev (port 3000)
:start_frontend_dev
echo.
echo [2/3] 启动 Frontend Dev Server (port 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /pid %%a /f >nul 2>&1
)
start "MfkAgent Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo   等待 Frontend 就绪...
set /a f_tries=0
:wait_frontend_ready
netstat -ano | findstr :3000 | findstr LISTENING >nul
if not errorlevel 1 goto frontend_ready
set /a f_tries+=1
if %f_tries% geq 45 goto start_electron
ping 127.0.0.1 -n 2 >nul
goto wait_frontend_ready

:frontend_ready
echo   Frontend 已就绪 (http://localhost:3000)

:: 4. 启动 Electron 桌面窗口
:start_electron
echo.
echo [3/3] 启动 Electron 桌面客户端...
:: 先清理旧 Electron 进程（单实例锁会导致新进程直接退出并聚焦旧窗口，
:: 必须先杀掉旧进程，否则修改后的主进程代码永远不会被加载）
echo   清理旧 Electron 进程...
taskkill /f /im electron.exe >nul 2>&1
ping 127.0.0.1 -n 2 >nul
set ELECTRON_DEV=true
set MFK_BACKEND_PORT=8001
start "MfkAgent Electron" cmd /c "cd /d %~dp0frontend && npx electron ."

echo.
echo ========================================
echo   MfkAgent Desktop 已成功拉起！
echo ========================================
echo.
echo 按任意键关闭本启动窗口...
pause >nul
