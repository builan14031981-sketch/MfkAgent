/**
 * 图片处理模块
 * 纯内存 NativeImage 毫秒级裁剪与 DataURL 转换，异步单次持久化
 */

const path = require("path");
const fs = require("fs");
const os = require("os");

/**
 * 根据屏幕截图内存对象和选中区域裁剪图片
 * @param {Array} screens - captureAllScreens 返回的屏幕数组（含 nativeImage）
 * @param {{x:number, y:number, width:number, height:number}} selection - 选中区域（屏幕坐标）
 * @returns {Promise<{filePath:string, dataUrl:string, width:number, height:number}>}
 */
async function cropSelection(screens, selection) {
  if (!screens || screens.length === 0) {
    throw new Error("No screen captures available");
  }

  // 找到选中区域中心所在的屏幕
  let targetScreen = screens[0];
  if (screens.length > 1) {
    const centerX = selection.x + selection.width / 2;
    const centerY = selection.y + selection.height / 2;
    for (const s of screens) {
      const b = s.bounds;
      if (centerX >= b.x && centerX < b.x + b.width && centerY >= b.y && centerY < b.y + b.height) {
        targetScreen = s;
        break;
      }
    }
  }

  const { bounds, scaleFactor, nativeImage: fullImage } = targetScreen;
  if (!fullImage) {
    throw new Error("Target screen has no image data");
  }

  // 约束在当前屏幕边界内
  const clamped = {
    x: Math.max(selection.x, bounds.x),
    y: Math.max(selection.y, bounds.y),
    width: Math.min(selection.x + selection.width, bounds.x + bounds.width) - Math.max(selection.x, bounds.x),
    height: Math.min(selection.y + selection.height, bounds.y + bounds.height) - Math.max(selection.y, bounds.y),
  };

  if (clamped.width <= 0 || clamped.height <= 0) {
    throw new Error("Invalid selection area");
  }

  // 将屏幕逻辑坐标转换为图片像素坐标（DPI 适配）
  const imgX = Math.round((clamped.x - bounds.x) * scaleFactor);
  const imgY = Math.round((clamped.y - bounds.y) * scaleFactor);
  const imgW = Math.round(clamped.width * scaleFactor);
  const imgH = Math.round(clamped.height * scaleFactor);

  // 纯内存高并发裁剪（~2-5ms）
  const cropped = fullImage.crop({ x: imgX, y: imgY, width: imgW, height: imgH });
  const dataUrl = cropped.toDataURL();
  const size = cropped.getSize();

  // 异步在后台持久化一份临时文件（不阻塞前台渲染，供需要本地路径的场景）
  const outputPath = path.join(os.tmpdir(), `mfk_screenshot_${Date.now()}.png`);
  fs.promises.writeFile(outputPath, cropped.toPNG()).catch((e) => {
    console.warn("[Screenshot] background async writeFile skipped:", e.message);
  });

  return {
    filePath: outputPath,
    dataUrl,
    width: size.width,
    height: size.height,
  };
}

module.exports = {
  cropSelection,
};
