/**
 * Backend connection config.
 *
 * When NEXT_PUBLIC_API_URL is set, the app can talk to the AutoFlow control
 * plane. When it is empty, the UI runs entirely on local mock data (the
 * default), so the desktop works with or without a backend.
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * Direct URL of the AI/ML server (used only for local file uploads such as an
 * employee roster for the reassign-work flow). Defaults to the local dev
 * server. The AI/ML server sends permissive CORS headers for this.
 */
export const AI_ML_BASE_URL =
  process.env.NEXT_PUBLIC_AI_ML_URL ?? "http://127.0.0.1:8770";

/** Whether a backend is configured. */
export const isBackendEnabled = (): boolean => API_BASE_URL.trim().length > 0;

/**
 * Dev bearer token. In this phase the backend uses mock auth, so any non-empty
 * token authenticates as the seeded operator. A real token provider replaces
 * this without changing callers.
 */
export const getAuthToken = (): string =>
  process.env.NEXT_PUBLIC_API_TOKEN ?? "dev";
