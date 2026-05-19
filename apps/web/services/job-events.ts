/**
 * Job event transport — polling-backed today, websocket-ready tomorrow.
 *
 * Components don't poll; they subscribe to a `JobEventStream`. The
 * implementation pulls from the API on an interval. When the backend
 * gets a real WebSocket endpoint, swap the `PollingTransport` for a
 * `SocketTransport` and the subscribers don't change.
 */
import type { Endpoints } from "@/lib/api/endpoints";
import type { JobView } from "@/lib/api/types";

export type JobEvent =
  | { type: "view"; view: JobView }
  | { type: "error"; error: unknown };

export interface JobEventTransport {
  subscribe(jobId: string, onEvent: (evt: JobEvent) => void): () => void;
}

export class PollingTransport implements JobEventTransport {
  constructor(
    private readonly endpoints: Endpoints,
    private readonly intervalMs: number = 4000,
  ) {}

  subscribe(jobId: string, onEvent: (evt: JobEvent) => void): () => void {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      if (cancelled) return;
      try {
        const view = await this.endpoints.getJobView(jobId);
        if (!cancelled) onEvent({ type: "view", view });
      } catch (error) {
        if (!cancelled) onEvent({ type: "error", error });
      } finally {
        if (!cancelled) timer = setTimeout(tick, this.intervalMs);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }
}

/**
 * Future: WebSocketTransport. Same interface; the subscribers don't
 * change. Once `/api/jobs/{id}/events` is live, the app's provider
 * switches to this implementation.
 */
export class WebSocketTransport implements JobEventTransport {
  constructor(private readonly url: string) {}
  subscribe(jobId: string, onEvent: (evt: JobEvent) => void): () => void {
    const ws = new WebSocket(`${this.url}/api/jobs/${jobId}/events`);
    ws.onmessage = (msg) => {
      try {
        const view = JSON.parse(msg.data) as JobView;
        onEvent({ type: "view", view });
      } catch (error) {
        onEvent({ type: "error", error });
      }
    };
    ws.onerror = (event) => onEvent({ type: "error", error: event });
    return () => ws.close();
  }
}
