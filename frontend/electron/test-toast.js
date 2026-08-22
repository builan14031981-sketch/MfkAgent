// ============================================================
// MfkAgent Toast 最小测试单元
//
// 运行： npx electron electron/test-toast.js
//
// 作用：直接用 Electron Notification API 弹一个系统 toast。
//   - 弹窗了 → 系统通知链路已打通（AUMID 快捷方式 OK）
//   - 没弹窗 → 检查 AUMID 快捷方式 / 系统通知设置 / 专注助手
// ============================================================
const { app, Notification } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

// Windows 下必须先设 AUMID（须与快捷方式中的 System.AppUserModel.ID 一致）
if (process.platform === "win32") {
  app.setAppUserModelId("com.mfkagent.app");
}

const SHORTCUT = path.join(
  process.env.APPDATA,
  "Microsoft", "Windows", "Start Menu", "Programs",
  "MfkAgent Dev.lnk"
);
const SCRIPT = path.join(__dirname, "dev-notification-shortcut.ps1");

function ensureShortcut(cb) {
  if (process.platform !== "win32" || fs.existsSync(SHORTCUT)) return cb();
  if (!fs.existsSync(SCRIPT)) {
    console.log("[test-toast] 未找到补建脚本，请确认 dev-notification-shortcut.ps1 存在");
    return cb();
  }
  console.log("[test-toast] 正在补建 AUMID 快捷方式...");
  spawn("powershell", [
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", SCRIPT,
    "-TargetExe", process.execPath,
  ], { windowsHide: true, stdio: "ignore" })
    .on("error", (e) => console.log("[test-toast] 补建失败:", e.message))
    .on("close", () => cb());
}

app.whenReady().then(() => {
  ensureShortcut(() => {
    setTimeout(() => {
      if (!Notification.isSupported()) {
        console.log("[test-toast] 当前平台不支持系统通知");
        app.quit();
        return;
      }
      const n = new Notification({
        title: "MfkAgent 测试通知",
        body: "如果你看到这条 toast，说明通知链路已打通",
      });
      n.on("click", () => app.quit());
      n.show();
      console.log("[test-toast] 已触发 Notification.show()");
      setTimeout(() => app.quit(), 6000); // 6 秒后自动退出
    }, 1500);
  });
});
