/**
 * Low-level HTTP client for the AutoFlow control plane.
 *
 * Thin wrapper over fetch that attaches auth, parses the standard error
 * envelope, and returns typed JSON. Transport concerns live here so the
 * repository adapter stays focused on shape mapping.
 */
import { API_BASE_URL, getAuthToken } from "@/lib/api/config";

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}/api/v1${path}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${getAuthToken()}`,
    ...(init.body ? { "Content-Type": "application/json" } : {}),
    ...(init.headers as Record<string, string> | undefined),
  };

  const res = await fetch(url, { ...init, headers });

  if (res.status === 204) return undefined as T;

  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const envelope = body as { error?: { code?: string; message?: string; details?: unknown } };
    const err = envelope?.error;
    throw new ApiError(
      err?.code ?? "HTTP_ERROR",
      err?.message ?? `Request failed (${res.status})`,
      res.status,
      err?.details,
    );
  }

  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
    request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      headers,
    }),
};
