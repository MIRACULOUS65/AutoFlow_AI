import type { DesktopApi } from "@/electron/preload";

declare global {
  interface Window {
    /**
     * The narrow desktop bridge injected by the Electron preload.
     * Undefined when the renderer runs in a plain browser (dev in a tab).
     */
    desktop?: DesktopApi;
  }
}

export {};
