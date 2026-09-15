/**
 * Upload a local file (e.g. an employee roster .xlsx) to the AI/ML server so
 * the reassign-work flow can read it on disk. The AI/ML server saves the bytes
 * to a temp directory and returns the absolute path, which is then passed to
 * the task as client_metadata.roster_path.
 *
 * Browsers do not expose a file's real filesystem path, so we send the bytes
 * (base64) and let the server materialise a real path it can open.
 */
import { AI_ML_BASE_URL } from "@/lib/api/config";

/** Base64-encode a File's bytes (browser-safe, chunked to avoid call-stack limits). */
async function fileToBase64(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < buf.length; i += chunk) {
    binary += String.fromCharCode(...buf.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export interface UploadResult {
  path: string;
  name: string;
  bytes: number;
}

/** Upload a roster file to the AI/ML server; returns the server-side path. */
export async function uploadRoster(file: File): Promise<UploadResult> {
  const content_b64 = await fileToBase64(file);
  const res = await fetch(`${AI_ML_BASE_URL}/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, content_b64 }),
  });
  const text = await res.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok || !body?.path) {
    throw new Error(body?.error || `upload failed (${res.status})`);
  }
  return { path: body.path as string, name: body.name as string, bytes: body.bytes as number };
}
