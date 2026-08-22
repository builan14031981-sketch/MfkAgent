/**
 * 截图遮罩窗口管理模块
 * 支持预创建窗口 + 复用，零延迟瞬时隐藏
 */

const { BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { getAllDisplaysBounds } = require("./capture-screen");

let overlayWindow = null;
let selectionResolve = null;

/**
 * 预创建截图窗口（应用启动时调用，隐藏状态，预加载 HTML）
 */
function precreateOverlayWindow() {
  if (overlayWindow) return;

  const bounds = getAllDisplaysBounds();

  overlayWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    focusable: true,
    show: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      backgroundThrottling: false,
    },
  });

  const overlayPath = path.join(__dirname, "overlay.html");
  overlayWindow.loadFile(overlayPath);

  overlayWindow.on("closed", () => {
    overlayWindow = null;
    if (selectionResolve) {
      const resolve = selectionResolve;
      selectionResolve = null;
      resolve(null);
    }
  });

  console.log("[Screenshot] overlay window precreated");
}

/**
 * 显示截图遮罩窗口（复用预创建的窗口）
 * @returns {Promise<{x:number, y:number, width:number, height:number}|null>} 选中区域
 */
function showOverlayWindow() {
  return new Promise((resolve) => {
    if (!overlayWindow) {
      precreateOverlayWindow();
    }

    selectionResolve = resolve;

    // 重新计算显示器边界（应对外接显示器插拔）
    const bounds = getAllDisplaysBounds();
    overlayWindow.setBounds(bounds);

    // 通知渲染进程重置选择状态
    try {
      overlayWindow.webContents.send("screenshot:reset");
    } catch (e) {
      // ignore
    }

    // 显示并聚焦
    overlayWindow.show();
    overlayWindow.focus();

    // 注册一次性 IPC：确认截图 → 瞬时隐藏并返回选区
    ipcMain.once("screenshot:confirm", (_event, selection) => {
      if (selectionResolve) {
        const resolveFn = selectionResolve;
        selectionResolve = null;
        if (overlayWindow) {
          overlayWindow.hide(); // 瞬时隐藏，零等待！
        }
        resolveFn(selection);
      }
    });

    // 注册一次性 IPC：取消截图
    ipcMain.once("screenshot:cancel", () => {
      if (selectionResolve) {
        const resolveFn = selectionResolve;
        selectionResolve = null;
        if (overlayWindow) {
          overlayWindow.hide();
        }
        resolveFn(null);
      }
    });
  });
}

/**
 * 关闭遮罩窗口
 */
function closeOverlayWindow() {
  if (overlayWindow) {
    try { overlayWindow.close(); } catch (e) {}
    overlayWindow = null;
  }
  if (selectionResolve) {
    const resolve = selectionResolve;
    selectionResolve = null;
    resolve(null);
  }
}

module.exports = {
  precreateOverlayWindow,
  showOverlayWindow,
  closeOverlayWindow,
};
