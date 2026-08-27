/**
 * 截图模块入口
 * 优化后架构：串行捕获（先截后显）+ 全内存裁剪 + 零磁盘阻塞
 *
 * 时序说明：
 * 1. 先捕获全屏图像（此时主窗口已隐藏，遮罩尚未显示，屏幕干净无 UI 元素）
 * 2. 再显示遮罩窗口，让用户拖选区域
 * 3. 用户确认后，从内存中已捕获的图像裁剪，毫秒级返回
 *
 * 串行相比原并发方案的收益：彻底消除遮罩十字线/提示文字/工具栏被截入的风险；
 * 性能差异可忽略（遮罩窗口预创建，show() 瞬时，捕获耗时两种方案都需等待）。
 */

const { captureAllScreens } = require("./capture-screen");
const { showOverlayWindow, closeOverlayWindow } = require("./overlay-window");
const { cropSelection } = require("./image-processor");

/**
 * 启动截图流程
 * @returns {Promise<{filePath:string, dataUrl:string, width:number, height:number}|null>}
 */
async function startScreenshot() {
  try {
    // 1. 先捕获所有显示器的全屏图像（全内存，零磁盘 I/O）
    //    此时主窗口已由调用方隐藏，遮罩窗口尚未显示，截图内容干净
    const screens = await captureAllScreens();
    if (!screens || screens.length === 0) {
      throw new Error("No screens captured");
    }

    // 2. 显示遮罩窗口，等待用户拖选区域并确认
    const selection = await showOverlayWindow();
    if (!selection) {
      // 用户取消（ESC / 右键 / 取消按钮）
      return null;
    }

    // 3. 从已捕获的内存图像中裁剪，毫秒级生成 DataURL（~5ms）
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
