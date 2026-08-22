/**
 * 截图遮罩窗口管理模块
 * 创建全屏透明窗口（直接看到后面的实时桌面），用户拖拽选择区域
 * 确认时返回选中区域的屏幕坐标，由调用方负责捕获并裁剪
 */

const { BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { getAllDisplaysBounds } = require("./capture-screen");

let overlayWindow = null;
let selectionResolve = null;

/**
 * 创建截图遮罩窗口
 * 窗口完全透明，用户可以看到后面的实时桌面，通过半透明遮罩+选框选择区域
 * @returns {Promise<{x:number, y:number, width:number, height:number}|null>} 选中区域（屏幕坐标），用户取消则返回 null
 */
function createOverlayWindow() {
  return new Promise((resolve) => {
    if (overlayWindow) {
      try { overlayWindow.close(); } catch (e) {}
      overlayWindow = null;
    }

    selectionResolve = resolve;
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
      show: true, // 立即显示，不等 HTML 加载完成，避免用户感知延迟
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        backgroundThrottling: false,
      },
    });

    const overlayPath = path.join(__dirname, "overlay.html");
    overlayWindow.loadFile(overlayPath);

    // 立即聚焦（HTML 加载完成后自然渲染交互）
    overlayWindow.focus();

    // 窗口关闭时清理
    overlayWindow.on("closed", () => {
      overlayWindow = null;
      if (selectionResolve) {
        const resolveFn = selectionResolve;
        selectionResolve = null;
        resolveFn(null);
      }
    });

    // 渲染进程通知确认：携带选中区域（屏幕坐标）
    ipcMain.once("screenshot:confirm", (_event, selection) => {
      if (selectionResolve) {
        const resolveFn = selectionResolve;
        selectionResolve = null;
        setTimeout(() => {
          if (overlayWindow) {
            try { overlayWindow.close(); } catch (e) {}
          }
        }, 100);
        resolveFn(selection);
      }
    });

    // 渲染进程通知取消
    ipcMain.once("screenshot:cancel", () => {
      if (selectionResolve) {
        const resolveFn = selectionResolve;
        selectionResolve = null;
        if (overlayWindow) {
          try { overlayWindow.close(); } catch (e) {}
        }
        resolveFn(null);
      }
    });
  });
}

/**
 * 关闭遮罩窗口（如果存在）
 */
function closeOverlayWindow() {
  if (overlayWindow) {
    try { overlayWindow.close(); } catch (e) {}
    overlayWindow = null;
  }
  if (selectionResolve) {
    const resolveFn = selectionResolve;
    selectionResolve = null;
    resolveFn(null);
  }
}

module.exports = {
  createOverlayWindow,
  closeOverlayWindow,
};
