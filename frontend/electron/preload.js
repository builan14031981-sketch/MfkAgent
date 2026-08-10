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
  openInFolder: (filePath) => ipcRenderer.invoke("open-in-folder", filePath),
});
