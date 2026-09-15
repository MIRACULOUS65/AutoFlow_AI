/**
 * Live execution event subscription (SSE) with reconnect replay.
 *
 * Uses the browser EventSource against the backend stream endpoint. On drop it
 * reconnects with ?after=<last sequence> so no events are missed — mirroring
 * the backend's reconnect contract (PRD §19, §27, §67).
 */
import { API_BASE_URL, getAuthToken } from "@/lib/api/config";
import { mapEvent } from "@/lib/api/mappers";
import type { ExecutionEvent } from "@/lib/types";

export interface EventSubscription {
  close: () => void;
}

export function subscribeToExecutionEvents(
  executionId: string,
  handlers: {
    onEvent: (event: ExecutionEvent, sequence: number) => void;
    onEnd?: (status: string) => void;
    onError?: (err: unknown) => void;
  },
  options: { after?: number } = {},
): EventSubscription {
  let lastSeq = options.after ?? 0;
  let source: EventSource | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (closed) return;
    // EventSource cannot set an Authorization header, so the token is passed
    // as a query param (the backend accepts access_token for SSE).
    const token = encodeURIComponent(getAuthToken());
    const url = `${API_BASE_URL}/api/v1/executions/${executionId}/stream?after=${lastSeq}&access_token=${token}`;
    source = new EventSource(url);

    // Named events (type is the SSE "event" field, e.g. "step.started").
    source.onmessage = (msg) => handleData(msg.data);
    // Some browsers deliver named events only via addEventListener.
    const forward = (e: MessageEvent) => handleData(e.data);
    [
      "task.created",
      "plan.created",
      "plan.validated",
      "step.started",
      "step.completed",
      "tool.started",
      "tool.completed",
      "verification.passed",
      "verification.failed",
      "approval.requested",
      "approval.granted",
      "recovery.started",
      "artifact.created",
      "execution.completed",
      "execution.failed",
      "execution.cancelled",
    ].forEach((name) => source?.addEventListener(name, forward as EventListener));

    source.addEventListener("stream.end", (e) => {
      try {
        const { status } = JSON.parse((e as MessageEvent).data);
        handlers.onEnd?.(status);
      } catch {
        handlers.onEnd?.("COMPLETE");
      }
      close();
    });

    source.onerror = (err) => {
      handlers.onError?.(err);
      // Reconnect from the last seen sequence after a short backoff.
      source?.close();
      if (!closed) {
        retry = setTimeout(connect, 1500);
      }
    };
  };

  const handleData = (raw: string) => {
    try {
      const payload = JSON.parse(raw);
      const event = mapEvent(payload);
      lastSeq = Math.max(lastSeq, payload.sequence ?? lastSeq);
      handlers.onEvent(event, lastSeq);
    } catch {
      /* ignore keepalives / malformed frames */
    }
  };

  const close = () => {
    closed = true;
    if (retry) clearTimeout(retry);
    source?.close();
    source = null;
  };

  connect();
  return { close };
}
