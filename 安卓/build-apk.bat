@echo off
REM ============================================================
REM MfkAgent 安卓端一键构建 APK（使用本机命令行构建环境）
REM 环境：JDK21 + Android SDK 36 @ C:\Users\Asus\android-build-env
REM 完整流程 = sync.bat（前端构建+同步）→ gradle assembleDebug
REM 产物：安卓\MfkAgent-debug.apk（构建后自动拷到本目录）
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/2] 同步前端产物（BUILD_TARGET=mobile，资源绝对路径）...
pushd ..\frontend
set BUILD_TARGET=mobile
call npm run build || goto :fail
popd
if exist www rmdir /s /q www
xcopy ..\frontend\out www /E /I /Q /Y || goto :fail
call npx cap sync android || goto :fail

echo [2/2] Gradle 构建 APK（首次约 3 分钟，增量更快）...
cmd /c "set JAVA_HOME=C:\Users\Asus\android-build-env\jdk-21&& C:\Users\Asus\android-build-env\gradle-8.14.3\bin\gradle.bat assembleDebug --no-daemon" || goto :fail

copy /Y android\app\build\outputs\apk\debug\app-debug.apk MfkAgent-debug.apk >nul
echo.
echo [完成] APK 已生成: E:\智慧项目\Mfkagent\安卓\MfkAgent-debug.apk
echo 传到手机安装即可（或手机插 USB 后执行: adb install -r MfkAgent-debug.apk）
pause
exit /b 0

:fail
echo [失败] 构建中断，请检查上方报错。
pause
exit /b 1
