const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const http = require("http");

let mainWindow;

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
  createWindow();
});

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
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    registerIpcHandlers();
    createWindow();
  }
});
