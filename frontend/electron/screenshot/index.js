/**
 * 截图模块入口
 * 极致性能架构：并发预捕获 + 全内存裁剪 + 零磁盘阻塞
 */

const { captureAllScreens } = require("./capture-screen");
const { showOverlayWindow, closeOverlayWindow } = require("./overlay-window");
const { cropSelection } = require("./image-processor");

/**
 * 启动截图流程
 * 1. 并发启动屏幕捕获与遮罩窗口显示（在用户拖选时，全屏捕获已在后台就绪）
 * 2. 用户点击确认瞬间，直接从内存中读取图像并裁剪
 * 3. 毫秒级生成 base64 data URL 返回渲染进程
 *
 * @returns {Promise<{filePath:string, dataUrl:string, width:number, height:number}|null>}
 */
async function startScreenshot() {
  try {
    // 1. 并发启动：一边展示遮罩选框，一边预先捕获全屏图像
    const capturePromise = captureAllScreens();
    const selectionPromise = showOverlayWindow();

    // 2. 等待用户完成选区并点击确认
    const selection = await selectionPromise;
    if (!selection) {
      // 用户取消
      return null;
    }

    // 3. 此时全屏捕获通常早已在后台完成，直接取结果
    const screens = await capturePromise;
    if (!screens || screens.length === 0) {
      throw new Error("No screens captured");
    }

    // 4. 纯内存毫秒级裁剪与 DataURL 生成（~5ms）
    const result = await cropSelection(screens, selection);
    return result;
  } catch (err) {
    console.error("[Screenshot] startScreenshot failed:", err);
    closeOverlayWindow();
    throw err;
  }
}

module.exports = {
  startScreenshot,
};
