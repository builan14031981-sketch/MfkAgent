const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage, shell, Notification } = require("electron");
const path = require("path");
const http = require("http");
const net = require("net");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");

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
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

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

app.whenReady().then(async () => {
  await startBackend();
  registerIpcHandlers();
  createTray();
  createWindow();
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
      });
      // 点击通知聚焦主窗口
      notif.on("click", () => {
        showWindow();
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
