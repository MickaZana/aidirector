/**
 * Typed fetch wrapper.
 *
 * - Auth: pulls a Clerk JWT and sends it as `Authorization: Bearer …`.
 * - Errors: turns non-2xx responses into typed `ApiError` instances
 *   with the status code + the response body for surfacing in the UI.
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
}
