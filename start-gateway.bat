@echo off
chcp 65001 >nul
title CLIProxyAPI 网关一键启动

echo ========================================
echo   CLIProxyAPI 网关一键启动
echo ========================================

:: ========== 配置区 ==========
set "V2RAY_PATH=E:\dowlaod\v2rayN-windows-64\v2rayN-windows-64\v2rayN.exe"
set "GATEWAY_PATH=C:\CLIProxyAPI\cli-proxy-api.exe"
set "GATEWAY_DIR=C:\CLIProxyAPI"
set "GATEWAY_PORT=8317"
set "GATEWAY_URL=http://127.0.0.1:8317/management.html"
:: ============================

:: [1/3] 启动 V2Ray 代理
echo.
echo [1/3] 启动 V2Ray 代理...
tasklist /fi "imagename eq v2rayN.exe" 2>nul | findstr /i "v2rayN.exe" >nul
if %errorlevel% equ 0 goto v2ray_running
if not exist "%V2RAY_PATH%" goto v2ray_notfound
start "" "%V2RAY_PATH%"
echo   V2Ray 已启动
echo   等待代理初始化 3秒...
timeout /t 3 /nobreak >nul
goto v2ray_done
:v2ray_notfound
echo   [警告] 未找到 V2Ray，请手动确认代理已开启
goto v2ray_done
:v2ray_running
echo   V2Ray 已在运行，跳过
:v2ray_done

:: [2/3] 启动 CLIProxyAPI 网关
echo.
echo [2/3] 启动 CLIProxyAPI 网关...
netstat -ano | findstr ":%GATEWAY_PORT%" | findstr LISTENING >nul
if %errorlevel% equ 0 goto gateway_running
if not exist "%GATEWAY_PATH%" goto gateway_notfound
cd /d "%GATEWAY_DIR%"
start "CLIProxyAPI" /min "%GATEWAY_PATH%" -config config.yaml
echo   CLIProxyAPI 已启动，最小化运行
echo   等待端口 %GATEWAY_PORT% 就绪...
set /a tries=0
:wait_port
netstat -ano | findstr ":%GATEWAY_PORT%" | findstr LISTENING >nul
if not errorlevel 1 goto port_ready
set /a tries+=1
if %tries% geq 15 goto port_timeout
timeout /t 1 /nobreak >nul
goto wait_port
:port_timeout
echo   [警告] 端口等待超时 15秒，网关可能启动失败
echo   请检查 CLIProxyAPI 窗口是否有报错
goto open_browser
:port_ready
echo   网关已就绪，端口 %GATEWAY_PORT%
goto open_browser
:gateway_notfound
echo   [错误] 未找到 CLIProxyAPI: %GATEWAY_PATH%
pause
exit /b 1
:gateway_running
echo   CLIProxyAPI 已在运行，端口 %GATEWAY_PORT%，跳过

:: [3/3] 打开浏览器管理面板
:open_browser
echo.
echo [3/3] 打开管理面板...
start "" "%GATEWAY_URL%"

echo.
echo ========================================
echo   启动完成！
echo   管理面板: %GATEWAY_URL%
echo   网关端口: %GATEWAY_PORT%
echo ========================================

:: [扩展点] 本地专属启动步骤（gateway_local_steps.bat，不上远程，其他机器克隆不受影响）
if exist "%~dp0gateway_local_steps.bat" call "%~dp0gateway_local_steps.bat"

echo.
timeout /t 2 /nobreak >nul
exit
