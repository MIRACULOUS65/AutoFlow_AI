/**
 * AutoFlow backend integration.
 *
 * The desktop UI depends on the local `lib/repository` (mock) by default so it
 * runs with zero backend. When NEXT_PUBLIC_API_URL is set, `backendRepository`
 * and `subscribeToExecutionEvents` provide the same domain model over HTTP+SSE
 * — the migration path from mock to live without changing page components.
 */
export { API_BASE_URL, isBackendEnabled, getAuthToken } from "@/lib/api/config";
export { api, ApiError } from "@/lib/api/client";
export type { Paginated } from "@/lib/api/client";
export { backendRepository } from "@/lib/api/repository";
export type { BackendRepository } from "@/lib/api/repository";
export {
  subscribeToExecutionEvents,
} from "@/lib/api/events";
export type { EventSubscription } from "@/lib/api/events";
