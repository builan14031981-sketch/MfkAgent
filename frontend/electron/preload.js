const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron,
  },
  selectDirectory: () => ipcRenderer.invoke("select-directory"),
  showNotification: (opts) => ipcRenderer.invoke("show-notification", opts),
  /**
   * 注册「导航到会话」回调：Electron 主进程点击通知时通过 IPC 推送 chatId，
   * 渲染进程收到后调用 next/navigation router.push 做客户端路由跳转，
   * 避免 mainWindow.loadURL 硬导航白屏。
   */
  onNavigateToChat: (callback) => {
    ipcRenderer.on("navigate-to-chat", (_event, chatId) => callback(chatId));
  },
  openInFolder: (filePath) => ipcRenderer.invoke("open-in-folder", filePath),
  openPath: (dirPath) => ipcRenderer.invoke("open-path", dirPath),
  // 自定义区域截图：类似 QQ/豆包的截图工具
  startScreenshot: () => ipcRenderer.invoke("start-screenshot"),
});
