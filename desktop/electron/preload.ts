import { contextBridge, ipcRenderer } from "electron";

/**
 * Secure bridge between the Electron main process and the renderer.
 * Only a narrow, explicit surface is exposed on `window.desktop`.
 * No raw Node.js, child_process, shell, or filesystem access is exposed.
 */
const desktopApi = {
  app: {
    getVersion: (): Promise<string> => ipcRenderer.invoke("app:getVersion"),
    getPlatform: (): Promise<NodeJS.Platform> =>
      ipcRenderer.invoke("app:getPlatform"),
  },
  window: {
    minimize: (): void => ipcRenderer.send("window:minimize"),
    maximize: (): void => ipcRenderer.send("window:maximize"),
    close: (): void => ipcRenderer.send("window:close"),
  },
} as const;

export type DesktopApi = typeof desktopApi;

contextBridge.exposeInMainWorld("desktop", desktopApi);
