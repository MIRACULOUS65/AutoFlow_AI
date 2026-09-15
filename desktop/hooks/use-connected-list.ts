"use client";

/**
 * Connected-mode list hook.
 *
 * In connected mode (NEXT_PUBLIC_API_URL set) this fetches a list resource from
 * the real Control Plane and returns it — so pages show REAL data (or an honest
 * empty list), never the static mock fixtures. In mock mode it returns the
 * provided local fallback so the desktop still works with zero backend.
 *
 * Usage:
 *   const workflows = useConnectedList(
 *     () => backendRepository.workflows(activeWs),
 *     mockWorkflows,
 *     [activeWs],
 *   );
 */
import { useEffect, useState } from "react";
import { isBackendEnabled } from "@/lib/api";

export function useConnectedList<T>(
  fetcher: () => Promise<T[]>,
  mockFallback: T[],
  deps: unknown[] = [],
): { items: T[]; loading: boolean; connected: boolean } {
  const connected = isBackendEnabled();
  // In connected mode start empty (real data replaces it); in mock mode use
  // the local fixtures immediately.
  const [items, setItems] = useState<T[]>(connected ? [] : mockFallback);
  const [loading, setLoading] = useState<boolean>(connected);

  useEffect(() => {
    if (!connected) {
      setItems(mockFallback);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetcher()
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch(() => {
        // Honest: on error show an empty list, not stale mock data.
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { items, loading, connected };
}
