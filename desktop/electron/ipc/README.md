# Electron IPC

IPC handlers are registered in `electron/main.ts` via `registerIpc()`.

As the desktop surface grows, extract feature-scoped handlers into modules here
(e.g. `window.ts`, `app.ts`) and register them from `main.ts`. Keep the exposed
renderer surface narrow and defined in `electron/preload.ts`.

Current channels:

| Channel            | Type     | Purpose                    |
| ------------------ | -------- | -------------------------- |
| `app:getVersion`   | invoke   | Return app version         |
| `app:getPlatform`  | invoke   | Return `process.platform`  |
| `window:minimize`  | send     | Minimize the main window   |
| `window:maximize`  | send     | Toggle maximize            |
| `window:close`     | send     | Close the main window      |
