/**
 * Typed fetch wrapper.
 *
 * - Auth: pulls a Clerk JWT and sends it as `Authorization: Bearer …`.
 * - Errors: turns non-2xx responses into typed `ApiError` instances
 *   with the status code + the response body for surfacing in the UI.
 * - Rate limits: on 429, dispatches a `rate-limited` custom DOM event
 *   with the `Retry-After` header so the UI can show toast + cooldown.
 * - No business logic. No retries. No optimistic state. Those live in
 *   `services/` or `hooks/`.
 *
 * The shape mirrors what the backend exposes (see `lib/api/types.ts`).
 */

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API request failed: ${status}`);
    this.status = status;
    this.body = body;
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  /** Returns a fresh Clerk JWT, or null if unauthenticated. */
  getToken: () => Promise<string | null>;
}

/**
 * Parses the `Retry-After` header value.
 * Returns seconds to wait, or 60 as a safe default.
 */
function parseRetryAfter(val: string | null): number {
  if (!val) return 60;
  const n = Number(val);
  return Number.isFinite(n) && n > 0 ? Math.ceil(n) : 60;
}

/** Custom event detail for 429 rate-limit notifications. */
export interface RateLimitEventDetail {
  retryAfterSeconds: number;
  path: string;
}

export const RATE_LIMIT_EVENT = "rate-limited" as const;

function dispatchRateLimit(retryAfterSeconds: number, path: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<RateLimitEventDetail>(RATE_LIMIT_EVENT, {
      detail: { retryAfterSeconds, path },
    }),
  );
}

/** Custom event detail for 402 billing-limit notifications. */
export interface BillingLimitEventDetail {
  path: string;
}

export const BILLING_LIMIT_EVENT = "billing-limit" as const;

function dispatchBillingLimit(path: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<BillingLimitEventDetail>(BILLING_LIMIT_EVENT, {
      detail: { path },
    }),
  );
}

export class ApiClient {
  constructor(private readonly opts: ApiClientOptions) {}

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await this.opts.getToken();
    const res = await fetch(`${this.opts.baseUrl}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });

    // Dispatch rate-limit event before throwing, so the UI can start
    // cooldown timers immediately.
    if (res.status === 429) {
      dispatchRateLimit(parseRetryAfter(res.headers.get("Retry-After")), path);
    }

    // Dispatch billing-limit event on 402, so the UI can show
    // a "Payment failed" / "Update billing" toast.
    if (res.status === 402) {
      dispatchBillingLimit(path);
    }

    const text = await res.text();
    let body: unknown = text;
    if (text.length > 0) {
      try {
        body = JSON.parse(text);
      } catch {
        // not JSON — keep raw text
      }
    }

    if (!res.ok) {
      throw new ApiError(res.status, body);
    }
    return body as T;
  }

  get<T>(path: string) {
    return this.request<T>(path, { method: "GET" });
  }

  post<T>(path: string, body: unknown) {
    return this.request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  delete<T = void>(path: string) {
    return this.request<T>(path, { method: "DELETE" });
  }
}
