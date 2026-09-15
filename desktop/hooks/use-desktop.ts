"use client";

import { useEffect, useState } from "react";

/**
 * Reads the narrow Electron bridge (window.desktop) exposed by the preload.
 * Returns { isDesktop, version, platform } and is safe in a plain browser tab.
 */
export function useDesktop() {
  const [version, setVersion] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string | null>(null);
  const isDesktop = typeof window !== "undefined" && !!window.desktop;

  useEffect(() => {
    if (!window.desktop) return;
    void window.desktop.app.getVersion().then(setVersion).catch(() => {});
    void window.desktop.app.getPlatform().then(setPlatform).catch(() => {});
  }, []);

  return {
    isDesktop,
    version,
    platform,
    minimize: () => window.desktop?.window.minimize(),
    maximize: () => window.desktop?.window.maximize(),
    close: () => window.desktop?.window.close(),
  };
}
