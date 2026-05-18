"use client";

import { useAuth } from "@clerk/nextjs";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useApi() {
  const { getToken } = useAuth();

  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await getToken();
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return (await res.json()) as T;
  }

  return { call };
}
