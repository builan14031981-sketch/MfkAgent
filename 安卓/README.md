# MfkAgent 安卓端工程（Capacitor 壳）

本目录是 MfkAgent 安卓 APP 的原生工程根目录。前端复用 `../frontend`（Next.js 静态导出），壳层用 Capacitor，架构见 `../docs/安卓端产品规划.md`。

## 目录结构

| 路径 | 说明 |
|---|---|
| `capacitor.config.json` | Capacitor 配置（appId `com.mfkagent.app`，webDir `www`） |
| `www/` | 前端静态产物（由 sync.bat 从 `frontend/out` 拷贝，**不要手改**） |
| `android/` | Android 原生工程（`npx cap add android` 生成，Android Studio 打开） |
| `sync.bat` | 一键同步：前端构建 → 拷贝 → cap sync |
| `../start-mobile.bat` | PC 端手机模式启动（监听 0.0.0.0:8001，局域网可访问） |

## 构建第一个 APK

**本机已配好命令行构建环境**（JDK 21 + Android SDK 36，位于 `C:\Users\Asus\android-build-env`，无需安装 Android Studio）：

```
双击 安卓\build-apk.bat
→ 产物: 安卓\MfkAgent-debug.apk（约 16MB）
```

传到手机安装即可；手机插 USB 开调试后也可直接 `adb install -r MfkAgent-debug.apk`
（adb 在 `C:\Users\Asus\android-build-env\android-sdk\platform-tools\`）。

> 环境备注：Gradle 与 Maven 依赖走腾讯/Aliyun 镜像（官方源在本机网络超时）；工程路径含中文已在
> `gradle.properties` 中豁免 AGP 路径检查（`android.overridePathCheck=true`）。
> 如需 Android Studio（调试、模拟器），Open 本目录下的 `android/` 即可，`local.properties` 已指向本机 SDK。

## 首次使用（配对流程）

1. PC 端双击 `start-mobile.bat` 启动后端（手机模式，监听 `0.0.0.0:8001`）；
2. PC 浏览器/桌面 APP 打开 **设置 → 连接手机**（`/pair` 页），屏幕出现二维码 + 6 位配对码；
3. 手机装好 APK 后打开 → 自动进入"连接你的电脑"页 → 点"扫描电脑上的二维码"对准 PC 屏幕（首次需授权相机），或改用手动输入地址 + 配对码；
4. 一次配对长期有效：token 存手机本地，之后打开 APP 即连；PC 端 `/pair` 页可随时吊销设备。

## 安全模型

- API key 全部留在 PC 后端，手机只持有"访问自家后端"的配对 token；
- 后端中间件：非本机回环来源访问 `/api/*` 必须带 token（`/api/mobile/pair/*` 握手除外）；
- 远程关机/重启/锁屏：手机端二次确认 + 写入沙箱审计日志（安全中心可查）；
- **M3（待做）**：跨公网访问走 Tailscale 组网（手机与 PC 各装一个），零端口暴露。

## 修改前端后更新 APP

```
安卓\sync.bat   → Android Studio 重新 Build
```

## 后端配套（已实现）

- `POST /api/mobile/pair/start|confirm` — 配对码签发与换取 token（码一次性，5 分钟有效）
- `GET /api/mobile/devices`、`POST /api/mobile/devices/{id}/revoke` — 设备管理与吊销
- `GET /api/mobile/system/status` — PC 工作状态
- `POST /api/mobile/system/power` — 关机/重启/锁屏（confirm=true 必填）
- `POST /api/mobile/system/wol` — 局域网内 Wake-on-LAN
- `WS /api/mobile/ws?token=` — AgentRun 状态变化推送（前台长连接方案）

## 已验证环境（2026-08-29）

- ✅ 本机命令行构建链：JDK21 + SDK36 + Gradle 8.14.3（`C:\Users\Asus\android-build-env`）
- ✅ 模拟器 Pixel6/API36 端到端跑通：安装 → 配对（127.0.0.1:8001 + 配对码）→ 首页/抽屉/真实数据全部正常

### 模拟器专属注意事项（真机不受影响）

1. **模拟器访问 PC 后端用 `adb reverse tcp:8001 tcp:8001`**，APP 里地址填 `127.0.0.1:8001`。
   这台 Windows 宿主 + AEHD 组合下，模拟器的 Chromium/okhttp 走 10.0.2.2 NAT 会中途断流
   （原生 nc 正常），adb reverse 完全绕开该缺陷。真机用局域网 IP，不受此影响。
2. `capacitor.config.json` 里 `plugins.CapacitorHttp.enabled: true` 把 fetch 走原生层
   （绕开 WebView 网络服务），副作用：**流式输出退化为整段返回**。真机上若 WebView 网络
   正常，可改回 `false` 恢复流式，二选一。
3. `server.allowNavigation: ["*"]` 与 `androidScheme: "http"` 同为 M1 过渡配置；
   M3 上 Tailscale/HTTPS 时收紧为固定域名并恢复 https。
