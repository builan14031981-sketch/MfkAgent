/**
 * 屏幕捕获模块
 * 使用 Electron desktopCapturer 全内存获取所有显示器的全屏 NativeImage 对象
 * 彻底消除磁盘 I/O 开销
 */

const { desktopCapturer, screen } = require("electron");

/**
 * 获取所有显示器的总边界（用于创建覆盖所有屏幕的遮罩窗口）
 * @returns {{x:number, y:number, width:number, height:number}}
 */
function getAllDisplaysBounds() {
  const displays = screen.getAllDisplays();
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const d of displays) {
    const b = d.bounds;
    minX = Math.min(minX, b.x);
    minY = Math.min(minY, b.y);
    maxX = Math.max(maxX, b.x + b.width);
    maxY = Math.max(maxY, b.y + b.height);
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

/**
 * 捕获所有显示器的全屏截图（全内存模式，零磁盘临时文件）
 * 每个显示器单独捕获，返回 { displayId, bounds, size, scaleFactor, nativeImage } 数组
 * @returns {Promise<Array<{displayId:string, bounds:object, size:object, scaleFactor:number, nativeImage:any}>>}
 */
async function captureAllScreens() {
  const displays = screen.getAllDisplays();
  if (displays.length === 0) return [];

  // 获取最大显示器高 DPI 尺寸
  const maxWidth = Math.max(...displays.map((d) => Math.round(d.size.width * (d.scaleFactor || 1))));
  const maxHeight = Math.max(...displays.map((d) => Math.round(d.size.height * (d.scaleFactor || 1))));

  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize: {
      width: maxWidth,
      height: maxHeight,
    },
  });

  const results = [];
  for (const display of displays) {
    const { width, height } = display.size;
    const scaleFactor = display.scaleFactor || 1;

    // 找到匹配当前 display 的 source（找不到则回退第一个）
    const source = sources.find((s) => s.display_id === String(display.id)) || sources[0];
    if (!source || !source.thumbnail) continue;

    results.push({
      displayId: String(display.id),
      bounds: { ...display.bounds },
      size: { width, height },
      scaleFactor,
      nativeImage: source.thumbnail, // 直接保留内存中的 NativeImage 对象
    });
  }

  return results;
}

module.exports = {
  getAllDisplaysBounds,
  captureAllScreens,
};
