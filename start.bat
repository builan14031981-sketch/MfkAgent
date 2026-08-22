@echo off
chcp 65001 >nul
title MfkAgent 一键启动
echo ========================================
echo   MfkAgent 一键启动（含进程守护）
echo ========================================

:: 后端 Python 解释器
set "PYTHON=C:\Users\Asus\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo.
echo [1/3] 启动 Backend 守护进程 (port 8001)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo   清理旧进程 PID %%a ...
    taskkill /pid %%a /f >nul 2>&1
)
if exist "%~dp0backend\.mfkagent_port" del "%~dp0backend\.mfkagent_port"

start "Backend Guardian" /min cmd /c "powershell.exe -NoProfile -ExecutionPolicy Bypass -File %~dp0backend_guardian.ps1"
echo   Backend 守护进程已启动

:: 等待后端端口就绪
echo.
echo   等待 Backend 启动...
set /a tries=0
:wait_port
netstat -ano | findstr :8001 | findstr LISTENING >nul
if not errorlevel 1 goto port_ready
set /a tries+=1
if %tries% geq 30 (
    echo   警告: Backend 启动超时，继续启动前端
    goto start_frontend
)
ping 127.0.0.1 -n 2 >nul
goto wait_port

:port_ready
echo   Backend 已就绪 (port 8001)

:start_frontend
echo.
echo [2/3] 启动 Frontend (port 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo   清理旧进程 PID %%a ...
    taskkill /pid %%a /f >nul 2>&1
)
start "MfkAgent Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"
echo   Frontend 已启动

echo.
echo [3/3] 等待所有服务就绪...
ping 127.0.0.1 -n 4 >nul

echo.
echo ========================================
echo   MfkAgent 启动完成！
echo.
echo   前端界面: http://localhost:3000
echo   后端 API: http://127.0.0.1:8001
echo.
echo   守护进程说明:
echo   - Backend 有独立守护进程在后台常驻
echo   - 进程意外退出后 3 秒自动重启
echo ========================================
echo.
echo 正在打开浏览器...
start http://localhost:3000
echo.
echo 按任意键关闭本启动窗口（服务将继续在后台运行）...
pause >nul
