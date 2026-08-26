const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage, shell, Notification } = require("electron");
const path = require("path");
const http = require("http");
const net = require("net");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
// 截图模块：自定义区域截图（类似 QQ/豆包）
const { startScreenshot } = require("./screenshot");
const { precreateOverlayWindow } = require("./screenshot/overlay-window");

// ── 单实例锁（Phase 8）：防止多开，第二个实例退出并聚焦已有窗口 ──
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  return;
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

// ── Windows 通知身份（Toast 归属）：与 electron-builder appId 保持一致 ──
// 必须在 app.whenReady() 前调用；未设置时 Windows Toast 会归到 "Electron" 默认身份，
// 导致通知不显示应用名/图标且无法进入系统通知设置管理
if (process.platform === "win32") {
  app.setAppUserModelId("com.mfkagent.app");
}

const BACKEND_HOST = "127.0.0.1";
let BACKEND_PORT = null; // 运行时动态探测
let mainWindow;
let tray;
// 由 Electron 拉起的后端子进程（外部已有服务时保持 null，不接管其生命周期）
let backendProcess = null;

/** 探测一个空闲 TCP 端口 */
function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, BACKEND_HOST, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function getBackendUrl() {
  return `http://${BACKEND_HOST}:${BACKEND_PORT}`;
}

/** 定位后端目录：dev 指向仓库 backend/，打包后指向 resources/backend */
function getBackendDir() {
  if (process.env.MFK_BACKEND_DIR) return process.env.MFK_BACKEND_DIR;
  if (process.env.ELECTRON_DEV === "true") {
    return path.join(__dirname, "..", "..", "backend");
  }
  return path.join(process.resourcesPath, "backend");
}

/** 定位后端可执行文件：优先 backend.exe（PyInstaller 产物），其次 Python 脚本 */
function getBackendExecutable() {
  const backendDir = getBackendDir();
  // 打包产物：backend.exe（PyInstaller --onefile）
  const exePath = path.join(backendDir, "dist", "backend.exe");
  if (fs.existsSync(exePath)) return { type: "exe", path: exePath, cwd: backendDir };
  // 回退：Python 脚本
  const py = process.env.MFK_PYTHON
    || (process.platform === "win32" ? "python" : "python3");
  return { type: "python", path: py, cwd: backendDir };
}

/** 探测后端健康端点（用于「端口已被手动服务占用」判断与启动就绪等待） */
function checkBackendHealth(timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(`${getBackendUrl()}/health`, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

/** 拉起后端并等待就绪。返回 true 表示后端可用。 */
async function startBackend() {
  // 1. 探测空闲端口
  if (!BACKEND_PORT) {
    BACKEND_PORT = process.env.MFK_BACKEND_PORT
      ? parseInt(process.env.MFK_BACKEND_PORT, 10)
      : await findFreePort();
    console.log(`[Electron] Using port ${BACKEND_PORT}`);
  }

  // 2. 检查是否已有后端在运行
  if (await checkBackendHealth()) {
    console.log(`[Electron] Backend already running at ${getBackendUrl()}, skip spawn`);
    backendProcess = null;
    return true;
  }

  // 3. 定位并启动后端
  const backendDir = getBackendDir();
  const exec = getBackendExecutable();

  if (exec.type === "exe") {
    // Phase 8：PyInstaller 打包产物 backend.exe
    console.log(`[Electron] Spawning backend.exe: ${exec.path} (port=${BACKEND_PORT})`);
    backendProcess = spawn(exec.path, [], {
      cwd: exec.cwd,
      env: { ...process.env, MFK_PORT: String(BACKEND_PORT), PYTHONUNBUFFERED: "1" },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } else {
    // 回退：Python + uvicorn
    const mainPy = path.join(backendDir, "main.py");
    if (!fs.existsSync(mainPy)) {
      console.warn(`[Electron] Backend entry not found: ${mainPy}`);
      return false;
    }
    const args = [
      "-m", "uvicorn", "main:app",
      "--host", BACKEND_HOST,
      "--port", String(BACKEND_PORT),
    ];
    console.log(`[Electron] Spawning backend: ${exec.path} ${args.join(" ")} (cwd=${backendDir})`);
    backendProcess = spawn(exec.path, args, {
      cwd: exec.cwd,
      env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
  }

  backendProcess.stdout.on("data", (d) => console.log(`[Backend] ${d.toString().trimEnd()}`));
  backendProcess.stderr.on("data", (d) => console.error(`[Backend] ${d.toString().trimEnd()}`));
  backendProcess.on("error", (err) => {
    console.error("[Electron] Backend failed to start:", err.message);
    backendProcess = null;
  });
  backendProcess.on("exit", (code, signal) => {
    console.log(`[Electron] Backend exited (code=${code}, signal=${signal})`);
    backendProcess = null;
  });

  // 4. 轮询等待就绪（最长 ~30s）
  for (let i = 0; i < 60; i++) {
    if (await checkBackendHealth()) {
      console.log(`[Electron] Backend ready at ${getBackendUrl()}`);
      return true;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  console.error("[Electron] Backend did not become ready in time");
  return false;
}

/** 干净终结后端进程树：Windows taskkill /T /F + POSIX SIGTERM/SIGKILL */
function stopBackend() {
  if (!backendProcess) return;
  const pid = backendProcess.pid;
  console.log(`[Electron] Stopping backend process tree (pid=${pid})`);
  try {
    if (process.platform === "win32") {
      // /T 终止整个进程树（含子进程），/F 强制终止
      spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      try {
        process.kill(-pid, "SIGTERM");
      } catch {
        try {
          process.kill(pid, "SIGTERM");
        } catch {
          process.kill(pid, "SIGKILL");
        }
      }
    }
  } catch (err) {
    console.error("[Electron] Failed to stop backend:", err.message);
  }
  backendProcess = null;
}

function waitForDevServer(url, maxRetries = 60) {
  return new Promise((resolve) => {
    let attempts = 0;
    function check() {
      attempts++;
      http.get(url, (res) => {
        if (res.statusCode === 200) {
          console.log(`[Electron] Dev server ready at ${url} (attempt ${attempts})`);
          resolve(true);
        } else {
          retry();
        }
      }).on("error", () => {
        retry();
      });

      function retry() {
        if (attempts >= maxRetries) {
          console.error(`[Electron] Dev server not ready after ${maxRetries}s`);
          resolve(false);
        } else {
          if (attempts === 1 || attempts % 10 === 0) {
            console.log(`[Electron] Waiting for ${url}... (${attempts}/${maxRetries})`);
          }
          setTimeout(check, 1000);
        }
      }
    }
    check();
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "MfkAgent",
    icon: nativeImage.createFromPath(path.join(__dirname, "assets", "app-icon.png")),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 强制设置窗口图标（Windows dev 模式下任务栏可能读 electron.exe 默认图标，setIcon 覆盖）
  try {
    mainWindow.setIcon(nativeImage.createFromPath(path.join(__dirname, "assets", "app-icon.png")));
  } catch (e) {
    console.warn("[Electron] setIcon failed:", e.message);
  }

  // 关闭按钮最小化到托盘（托盘「退出」才真正退出）
  mainWindow.on("close", (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.webContents.on("did-fail-load", (event, code, desc, url) => {
    console.error(`[Electron] Failed to load ${url}: ${code} - ${desc}`);
  });

  mainWindow.webContents.on("did-finish-load", () => {
    console.log("[Electron] Page loaded successfully");
  });

  // 拦截外部链接：在系统默认浏览器中打开，禁止在 Electron 内部窗口导航
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    const currentUrl = mainWindow.webContents.getURL();
    // 仅拦截非同源的外部跳转
    try {
      const currentOrigin = new URL(currentUrl).origin;
      const targetOrigin = new URL(url).origin;
      if (currentOrigin !== targetOrigin) {
        event.preventDefault();
        shell.openExternal(url);
      }
    } catch {
      // URL 解析失败则放行
    }
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    console.log("[Electron] Window shown");
  });

  const isDev = process.env.ELECTRON_DEV === "true";

  if (isDev) {
    const ready = await waitForDevServer("http://localhost:3000");
    if (ready) {
      mainWindow.loadURL("http://localhost:3000");
      mainWindow.webContents.openDevTools();
    } else {
      mainWindow.loadURL(
        "data:text/html," +
        encodeURIComponent(
          "<html><body style='font-family:sans-serif;padding:40px;text-align:center'>" +
          "<h1>Dev server not ready</h1>" +
          "<p>Please ensure Next.js is running on port 3000</p>" +
          "<p>Run: <code>cd frontend && npm run dev</code></p>" +
          "</body></html>"
        )
      );
      mainWindow.show();
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, "../out/index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

/**
 * Windows dev 模式通知身份补建：Windows 10+ 要求 Toast 的 AppUserModelId 必须对应
 * 一个带 System.AppUserModel.ID 属性的开始菜单快捷方式，否则通知被系统静默丢弃。
 * 打包版由 NSIS 安装器自动创建；dev 模式首次启动时用脚本补建（已存在则跳过）。
 */
function ensureDevNotificationShortcut() {
  if (process.platform !== "win32" || process.env.ELECTRON_DEV !== "true") return;
  try {
    const programsDir = path.join(process.env.APPDATA || "", "Microsoft", "Windows", "Start Menu", "Programs");
    const shortcutPath = path.join(programsDir, "MfkAgent Dev.lnk");
    if (fs.existsSync(shortcutPath)) return;
    const script = path.join(__dirname, "dev-notification-shortcut.ps1");
    if (!fs.existsSync(script)) return;
    console.log("[Electron] Creating dev notification shortcut (Windows Toast identity)...");
    spawn("powershell", [
      "-NoProfile", "-ExecutionPolicy", "Bypass",
      "-File", script,
      "-TargetExe", process.execPath,
    ], { windowsHide: true, stdio: "ignore" }).on("error", (err) => {
      console.warn("[Electron] dev notification shortcut failed:", err.message);
    });
  } catch (err) {
    console.warn("[Electron] ensureDevNotificationShortcut failed:", err.message);
  }
}

app.whenReady().then(async () => {
  ensureDevNotificationShortcut();
  await startBackend();
  registerIpcHandlers();
  createTray();
  createWindow();
  // 预创建截图窗口（隐藏状态，预加载 HTML），点击截图时可立即显示，避免创建延迟
  precreateOverlayWindow();
});

// 应用退出前干净终结后端进程树（同步阻塞，保证退出时无残留进程）
app.on("before-quit", () => {
  app.isQuitting = true;
  stopBackend();
});

app.on("will-quit", () => {
  stopBackend();
});

// 兜底：任何路径导致的进程退出都尽力清理（含崩溃/异常退出）
process.on("exit", () => {
  stopBackend();
});

/** 系统托盘：常驻任务栏图标，右键菜单（显示 / 退出），左键恢复窗口 */
function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, "assets", "tray-icon.png"));
  tray = new Tray(icon);
  tray.setToolTip("MfkAgent");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "显示 MfkAgent", click: showWindow },
      { type: "separator" },
      { label: "退出", click: () => { app.isQuitting = true; app.quit(); } },
    ])
  );
  tray.on("click", showWindow);
}

function showWindow() {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

// 原生目录选择：供渲染进程关联本地项目工作区。
function registerIpcHandlers() {
  if (ipcMain.listenerCount("select-directory") > 0 || ipcMain.eventNames().includes("select-directory")) {
    console.warn("[Electron] 'select-directory' handler already registered, skip.");
    return;
  }
  ipcMain.handle("select-directory", async () => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        title: "选择项目文件夹",
        properties: ["openDirectory", "createDirectory"],
      });
      if (result.canceled || result.filePaths.length === 0) {
        return null;
      }
      return result.filePaths[0];
    } catch (err) {
      console.error("[Electron] select-directory failed:", err);
      return null;
    }
  });
  console.log("[Electron] IPC handler 'select-directory' registered");

  // 原生 Windows 通知：后台任务完成 / 审批请求时唤起右下角 Toast + 提示音
  // 节流在渲染进程侧控制（3 秒内不重复触发音效），主进程仅负责展示
  ipcMain.handle("show-notification", async (_evt, opts) => {
    try {
      if (!Notification.isSupported()) {
        console.warn("[Electron] Notification not supported on this platform");
        return false;
      }
      const notif = new Notification({
        title: opts.title || "MfkAgent",
        body: opts.body || "",
        silent: opts.silent === true, // 渲染进程自行播放音效时设 true 避免双重音
        // Windows: persistent=true（需用户交互：审批/抉择/错误）时不自动消失，
        // 保持显示直到用户点击/关闭；短显信息类（完成）用默认时长
        timeoutType: opts.persistent === true ? "never" : "default",
      });
      // 点击通知聚焦主窗口；带 chatId 时通过 IPC 推送导航事件给渲染进程，
      // 由渲染进程用 next/navigation router.push 做客户端路由，避免 loadURL 硬导航白屏
      notif.on("click", () => {
        showWindow();
        if (opts && Number.isFinite(opts.chatId)) {
          try {
            mainWindow.webContents.send("navigate-to-chat", Number(opts.chatId));
          } catch (err) {
            console.warn("[Electron] navigate on notification click failed:", err.message);
          }
        }
      });
      notif.show();
      return true;
    } catch (err) {
      console.error("[Electron] show-notification failed:", err);
      return false;
    }
  });
  console.log("[Electron] IPC handler 'show-notification' registered");

  // 在系统文件管理器中打开文件/文件夹
  ipcMain.handle("open-in-folder", async (_evt, filePath) => {
    try {
      if (!filePath || typeof filePath !== "string") return false;
      const absPath = path.isAbsolute(filePath) ? filePath : path.resolve(filePath);
      if (!fs.existsSync(absPath)) {
        console.warn("[Electron] open-in-folder: path not found:", absPath);
        return false;
      }
      shell.showItemInFolder(absPath);
      return true;
    } catch (err) {
      console.error("[Electron] open-in-folder failed:", err);
      return false;
    }
  });
  console.log("[Electron] IPC handler 'open-in-folder' registered");

  // 直接打开系统文件管理器进入指定目录（区别于 showItemInFolder 的“在父目录中选中”）
  ipcMain.handle("open-path", async (_evt, dirPath) => {
    try {
      if (!dirPath || typeof dirPath !== "string") {
        console.warn("[Electron] open-path: invalid path:", dirPath);
        return false;
      }
      const absPath = path.isAbsolute(dirPath) ? dirPath : path.resolve(dirPath);
      if (!fs.existsSync(absPath)) {
        console.warn("[Electron] open-path: path not found:", absPath);
        return false;
      }
      // shell.openPath 返回 Promise<string>：成功返回空字符串，失败返回错误信息
      const errMsg = await shell.openPath(absPath);
      if (errMsg) {
        console.error("[Electron] open-path failed:", errMsg);
        return false;
      }
      return true;
    } catch (err) {
      console.error("[Electron] open-path exception:", err);
      return false;
    }
  });
  console.log("[Electron] IPC handler 'open-path' registered");

  // 自定义区域截图：类似 QQ/豆包的截图工具，拖拽选区域后返回图片文件
  ipcMain.handle("start-screenshot", async () => {
    try {
      console.log("[Electron] start-screenshot: begin");
      const result = await startScreenshot();
      if (!result) {
        console.log("[Electron] start-screenshot: cancelled by user");
        return { success: false, cancelled: true };
      }
      console.log("[Electron] start-screenshot: success", result.filePath, `${result.width}x${result.height}`);
      return { success: true, ...result };
    } catch (err) {
      console.error("[Electron] start-screenshot failed:", err);
      return { success: false, error: err.message };
    }
  });
  console.log("[Electron] IPC handler 'start-screenshot' registered");
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin" && app.isQuitting) {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    registerIpcHandlers();
    createWindow();
  }
});
