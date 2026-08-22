@echo off
chcp 65001 >nul
title CLIProxyAPI 网关一键停止

echo ========================================
echo   CLIProxyAPI 网关一键停止
echo ========================================

:: [1/2] 停止 CLIProxyAPI
echo.
echo [1/2] 停止 CLIProxyAPI 网关...
tasklist /fi "imagename eq cli-proxy-api.exe" 2>nul | findstr /i "cli-proxy-api.exe" >nul
if %errorlevel% equ 0 (
    taskkill /f /im cli-proxy-api.exe >nul 2>&1
    if %errorlevel% equ 0 (
        echo   CLIProxyAPI 已停止
    ) else (
        echo   [警告] CLIProxyAPI 停止失败，请手动结束进程
    )
) else (
    echo   CLIProxyAPI 未运行，跳过
)

:: [2/2] 停止 V2Ray
echo.
echo [2/2] 停止 V2Ray 代理...
tasklist /fi "imagename eq v2rayN.exe" 2>nul | findstr /i "v2rayN.exe" >nul
if %errorlevel% equ 0 (
    taskkill /f /im v2rayN.exe >nul 2>&1
    if %errorlevel% equ 0 (
        echo   V2Ray 已停止
    ) else (
        echo   [警告] V2Ray 停止失败，请手动结束进程
    )
) else (
    echo   V2Ray 未运行，跳过
)

echo.
echo ========================================
echo   停止完成！
echo ========================================
echo.
timeout /t 2 /nobreak >nul
exit
