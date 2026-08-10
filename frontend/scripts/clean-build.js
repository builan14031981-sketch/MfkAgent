/**
 * Phase 8: 打包前清理脚本。
 * 清除旧构建产物，确保输出目录干净无源码泄露。
 * 由 electron-builder.yml 的 beforePack 钩子调用。
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

/** 安全删除目录（仅删除构建产物目录，不碰源码） */
function safeRemove(dir) {
  const fullPath = path.join(ROOT, dir);
  if (fs.existsSync(fullPath)) {
    console.log(`[clean-build] Removing ${dir}...`);
    fs.rmSync(fullPath, { recursive: true, force: true });
    console.log(`[clean-build]   -> ${dir} removed`);
  }
}

/** 安全删除文件 */
function safeRemoveFile(file) {
  const fullPath = path.join(ROOT, file);
  if (fs.existsSync(fullPath)) {
    console.log(`[clean-build] Removing ${file}...`);
    fs.unlinkSync(fullPath);
    console.log(`[clean-build]   -> ${file} removed`);
  }
}

// 清理构建产物目录
safeRemove("release");
safeRemove("dist");
safeRemove(".next");

// 清理 electron-builder 缓存
const cacheDir = path.join(require("os").homedir(), "AppData", "Local", "electron-builder", "Cache");
if (fs.existsSync(cacheDir)) {
  console.log("[clean-build] Electron-builder cache exists (not cleaned, reuse for faster builds)");
}

console.log("[clean-build] Done. Output directories are clean.");