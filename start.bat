@echo off
chcp 65001 >nul
title MfkAgent 一键启动

echo ========================================
echo   MfkAgent 智能工作站 一键启动
echo ========================================
echo.

:: 1. 自动定位 Python 解释器
set "MFK_PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%MFK_PYTHON%" (
    set "MFK_PYTHON=python"
)

:: 2. 清理旧冲突进程与旧端口并启动后端
echo [1/2] 正在清理旧进程与启动后端服务 (端口 8001)...
taskkill /f /im backend.exe >nul 2>&1
taskkill /f /im MfkAgent.exe >nul 2>&1
taskkill /f /im electron.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    taskkill /pid %%a /f >nul 2>&1
)
if exist "%~dp0backend\.mfkagent_port" del "%~dp0backend\.mfkagent_port"

cd /d "%~dp0backend"
start "MfkAgent Backend" /min "%MFK_PYTHON%" main.py

:: 等待后端就绪
set /a tries=0
:wait_backend
netstat -ano | findstr :8001 | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto backend_ready
set /a tries+=1
if %tries% geq 25 goto backend_ready
ping 127.0.0.1 -n 2 >nul
goto wait_backend

:backend_ready
echo   后端服务已就绪 (http://127.0.0.1:8001)

:: 3. 启动前端界面
echo.
echo [2/2] 正在启动前端开发服务 (端口 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /pid %%a /f >nul 2>&1
)

cd /d "%~dp0frontend"
start "MfkAgent Frontend" cmd /c "npm run dev"

:: 轮询等待前端真正就绪后再打开浏览器
echo   正在等待前端服务编译就绪 (http://localhost:3000)...
set /a f_tries=0
:wait_frontend
netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto frontend_ready
set /a f_tries+=1
if %f_tries% geq 35 goto frontend_ready
ping 127.0.0.1 -n 2 >nul
goto wait_frontend

:frontend_ready
echo   前端服务已就绪，正在打开浏览器...
start http://localhost:3000

echo.
echo ========================================
echo   启动完成！
echo   访问地址: http://localhost:3000
echo   后端接口: http://127.0.0.1:8001
echo ========================================
echo.
echo 本窗口可关闭，后台服务将继续运行。
echo 如需关闭本窗口，按任意键即可...
pause >nul
exit
