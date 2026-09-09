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

:: 2. 清理旧端口占用并启动后端
echo [1/2] 正在启动后端服务 (端口 8001)...
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
if %tries% geq 20 goto backend_ready
ping 127.0.0.1 -n 2 >nul
goto wait_backend

:backend_ready
echo   后端服务已就绪！

:: 3. 启动前端界面
echo.
echo [2/2] 正在启动前端客户端...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /pid %%a /f >nul 2>&1
)

cd /d "%~dp0frontend"
start "MfkAgent Frontend" /min cmd /c "npm run dev"

:: 等待前端并打开浏览器
ping 127.0.0.1 -n 3 >nul
start http://localhost:3000

echo.
echo ========================================
echo   启动完成！
echo   访问地址: http://localhost:3000
echo   后端接口: http://127.0.0.1:8001
echo ========================================
echo.
echo 本窗口可关闭，后台服务将继续运行。
timeout /t 5 >nul
exit
