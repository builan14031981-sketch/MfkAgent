/**
 * 截图模块入口
 * 流程：创建透明遮罩窗口（看到实时桌面）→ 用户拖拽选区域 → 确认时才捕获屏幕并裁剪
 * 类似 QQ/豆包的截图体验，不需要预先暂停桌面
 */

const { captureAllScreens, cleanupTempFiles } = require("./capture-screen");
const { createOverlayWindow, closeOverlayWindow } = require("./overlay-window");
const { cropSelection, toDataURL, getImageSize } = require("./image-processor");

/**
 * 启动截图流程
 * 1. 立即显示全屏透明遮罩窗口（用户看到实时桌面）
 * 2. 用户拖拽选择区域
 * 3. 确认时才捕获屏幕并裁剪选中区域
 * 4. 返回截图文件路径和 base64 data URL
 *
 * @returns {Promise<{filePath:string, dataUrl:string, width:number, height:number}|null>}
 *          用户取消则返回 null
 */
async function startScreenshot() {
  let screens = [];
  let tempFiles = [];

  try {
    // Step 1: 立即显示透明遮罩窗口，用户看到实时桌面，选择区域
    // 不需要预先捕获屏幕，启动速度快
    const selection = await createOverlayWindow();
    if (!selection) {
      // 用户取消
      return null;
    }

    // Step 2: 用户确认后，才捕获屏幕并裁剪选中区域
    screens = await captureAllScreens();
    if (screens.length === 0) {
      throw new Error("No screens captured");
    }
    tempFiles = screens.map((s) => s.imagePath);

    // Step 3: 裁剪选中区域
    const outputPath = await cropSelection(screens, selection);

    // Step 4: 获取截图信息
    const dataUrl = toDataURL(outputPath);
    const size = getImageSize(outputPath);

    // 清理临时屏幕截图文件（保留输出文件）
    cleanupTempFiles(tempFiles);

    return {
      filePath: outputPath,
      dataUrl,
      width: size.width,
      height: size.height,
    };
  } catch (err) {
    console.error("[Screenshot] startScreenshot failed:", err);
    cleanupTempFiles(tempFiles);
    closeOverlayWindow();
    throw err;
  }
}

module.exports = {
  startScreenshot,
};
