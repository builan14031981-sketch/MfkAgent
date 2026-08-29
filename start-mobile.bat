@echo off
REM ============================================================
REM MfkAgent 手机模式启动脚本（安卓端 M1/M2）
REM 与 start.bat 的唯一区别：MFK_HOST=0.0.0.0（局域网可访问）
REM 手机首次连接：桌面浏览器打开 http://127.0.0.1:8001 前端的 /pair 页面
REM （或直接运行前端后在设置里打开"连接手机"）扫码配对。
REM 安全：非配对设备无法访问任何 /api/* 接口（回环除外）。
REM ============================================================
chcp 65001 >nul
title MfkAgent (Mobile Mode)
set MFK_HOST=0.0.0.0
set MFK_PORT=8001

echo [MfkAgent] 以手机模式启动后端（监听 0.0.0.0:8001）...
echo [MfkAgent] 本机局域网地址（手机端配对用）:
ipconfig | findstr /i "IPv4"

cd /d "%~dp0backend"
python main.py
pause
