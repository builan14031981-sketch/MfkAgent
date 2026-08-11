"use client";

/**
 * 本地文件夹选择：
 * - Electron 环境优先调用 window.electronAPI.selectDirectory()（原生对话框，返回绝对路径）。
 * - 非 Electron 环境 / IPC 未注册 / 调用失败时，降级为 HTML5 <input webkitdirectory>
 *   （仅能拿到相对路径，返回首层目录名）。
 */

function isElectron(): boolean {
  return typeof window !== "undefined" && typeof window.electronAPI?.selectDirectory === "function";
}

export async function selectDirectory(): Promise<string | null> {
  if (isElectron()) {
    try {
      const dir = await window.electronAPI!.selectDirectory!();
      if (dir) return dir;
    } catch (err) {
      // IPC 失败（如 No handler registered for 'select-directory'）→ 降级浏览器方案
      console.error("Electron selectDirectory failed, falling back to browser:", err);
    }
  }
  return selectDirectoryBrowserFallback();
}

/** HTML5 webkitdirectory 降级：返回首层目录名（无法拿到绝对路径） */
function selectDirectoryBrowserFallback(): Promise<string | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.setAttribute("webkitdirectory", "");
    input.setAttribute("directory", "");
    input.style.display = "none";

    const cleanup = () => {
      if (input.parentNode) {
        document.body.removeChild(input);
      }
    };

    input.addEventListener("change", () => {
      const file = input.files?.[0];
      cleanup();
      resolve(file && file.webkitRelativePath ? file.webkitRelativePath.split("/")[0] : null);
    });

    // 用户取消选择时 resolve null（cancel 事件兼容性：现代浏览器均支持）
    input.addEventListener("cancel", () => {
      cleanup();
      resolve(null);
    });

    document.body.appendChild(input);
    input.click();
    // 注意：不能在 click() 后立即 removeChild，
    // 否则 input 从 DOM 移除后 change/cancel 事件永远不会触发，Promise 永不 resolve。
  });
}
