const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage } = require("electron");
const path = require("path");
const http = require("http");

let mainWindow;
let tray;

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

app.whenReady().then(() => {
  registerIpcHandlers();
  createTray();
  createWindow();
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
// 必须在 app ready 后注册，确保 preload 加载时句柄已就绪。
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
}

app.on("window-all-closed", () => {
  // 有托盘时窗口关闭是隐藏而非销毁；仅当显式「退出」时才真正退出
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
