import { app, BrowserWindow, ipcMain, protocol, net, shell } from "electron";
import * as path from "path";
import * as fs from "fs";
import { pathToFileURL } from "url";

/**
 * AutoFlow desktop — main process.
 *
 * Responsibilities are intentionally thin: window management, lifecycle, a
 * small set of secure IPC handlers, and serving the packaged static frontend
 * through a custom `app://` protocol. No AI, orchestration, or business logic
 * lives here. The renderer (Next.js) owns the product experience.
 */

const isDev = process.env.NODE_ENV === "development";
const DEV_URL = "http://localhost:3000";
const APP_SCHEME = "app";

let mainWindow: BrowserWindow | null = null;

// Register the custom scheme as privileged before app ready so it behaves like
// https (secure context, fetch, streaming) for the static export.
protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
    },
  },
]);

/** Resolve a request path against the exported `out/` directory. */
function resolveStaticFile(requestPath: string): string {
  // When packaged, `out/` is asar-unpacked (see electron-builder.yml). The
  // network stack does not perform asar redirection, so point at the on-disk
  // `app.asar.unpacked` copy explicitly.
  const baseDir = __dirname.replace(
    `app.asar${path.sep}`,
    `app.asar.unpacked${path.sep}`,
  );
  const outDir = path.join(baseDir, "..", "out");
  // Strip query/hash and leading slash.
  let rel = decodeURIComponent(requestPath.split("?")[0].split("#")[0]);
  rel = rel.replace(/^\/+/, "");
  if (rel === "") rel = "index.html";

  let filePath = path.join(outDir, rel);

  // Directory or extensionless route → try trailing-slash index.html.
  if (!path.extname(filePath)) {
    const asIndex = path.join(filePath, "index.html");
    if (fs.existsSync(asIndex)) return asIndex;
    const asHtml = `${filePath}.html`;
    if (fs.existsSync(asHtml)) return asHtml;
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    return filePath;
  }

  // SPA fallback for unknown (e.g. runtime-created task) routes.
  return path.join(outDir, "index.html");
}

function registerAppProtocol(): void {
  protocol.handle(APP_SCHEME, (request) => {
    const url = new URL(request.url);
    const filePath = resolveStaticFile(url.pathname);
    return net.fetch(pathToFileURL(filePath).toString());
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1180,
    minHeight: 760,
    show: false,
    backgroundColor: "#0f0f0f",
    title: "AutoFlow AI",
    autoHideMenuBar: true,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  if (isDev) {
    void mainWindow.loadURL(DEV_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    void mainWindow.loadURL(`${APP_SCHEME}://app/index.html`);
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  // Open external links in the OS browser, never inside the app window.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function registerIpc(): void {
  ipcMain.handle("app:getVersion", () => app.getVersion());
  ipcMain.handle("app:getPlatform", () => process.platform);

  ipcMain.on("window:minimize", () => mainWindow?.minimize());
  ipcMain.on("window:maximize", () => {
    if (!mainWindow) return;
    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    else mainWindow.maximize();
  });
  ipcMain.on("window:close", () => mainWindow?.close());
}

app.whenReady().then(() => {
  if (!isDev) registerAppProtocol();
  registerIpc();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
