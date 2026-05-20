"use client";

/**
 * Runtime API client factory.
 *
 * Hooks call `useApi()` to get the `Endpoints` instance for the current
 * Clerk session + the runtime mode (`live` vs `fixtures`). They do NOT
 * call `new ApiClient()` themselves — that would leak the auth strategy
 * into every hook.
 *
 * Mode selection:
 *   - `NEXT_PUBLIC_API_URL` set, non-empty, and not `"fixtures"` → live.
 *     Hooks fetch from the API; fixtures are only used as a last-resort
 *     fallback when a live call throws (so the UI degrades gracefully
 *     during a dev session with the API down).
 *   - otherwise → fixtures-only. No network calls. Useful for storybook,
 *     CI, and static prerendering.
 *
 * The fallback path is intentionally narrow: hooks log `error` and
 * surface a `fixturesUsed=true` flag so the UI can show a "demo data"
 * banner. Production has the env var set, so the fallback path stays
 * dormant outside of local dev.
 */
import { useAuth } from "@clerk/nextjs";
import { useMemo } from "react";
import { ApiClient } from "./client";
import { Endpoints } from "./endpoints";

export type RuntimeMode = "live" | "fixtures";

export function getRuntimeMode(): RuntimeMode {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url || url === "fixtures") return "fixtures";
  return "live";
}

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "";
}

export interface UseApi {
  endpoints: Endpoints | null;
  mode: RuntimeMode;
  baseUrl: string;
}

export function useApi(): UseApi {
  const { getToken } = useAuth();
  const mode = getRuntimeMode();
  const baseUrl = getApiBaseUrl();

  const endpoints = useMemo<Endpoints | null>(() => {
    if (mode !== "live") return null;
    const client = new ApiClient({
      baseUrl,
      getToken: async () => {
        try {
          return await getToken();
        } catch {
          return null;
        }
      },
    });
    return new Endpoints(client);
  }, [mode, baseUrl, getToken]);

  return { endpoints, mode, baseUrl };
}
