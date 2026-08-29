@echo off
REM ============================================================
REM MfkAgent 安卓端一键同步：前端构建 → 拷贝静态产物 → 写入安卓工程
REM 之后用 Android Studio 打开 android/ 目录构建 APK（见 README.md）
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] 构建前端静态导出（frontend ^> npm run build）...
pushd ..\frontend
call npm run build || goto :fail
popd

echo [2/3] 拷贝静态产物 frontend\out ^> www ...
if exist www rmdir /s /q www
xcopy ..\frontend\out www /E /I /Q /Y || goto :fail

echo [3/3] 同步进安卓工程（cap sync）...
call npx cap sync android || goto :fail

echo.
echo [完成] android/ 工程已更新。用 Android Studio 打开 安卓\android\ 构建 APK。
pause
exit /b 0

:fail
echo [失败] 同步中断，请检查上方报错。
pause
exit /b 1
