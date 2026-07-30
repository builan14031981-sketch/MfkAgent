const { app, BrowserWindow } = require("electron");
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

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
