"use client";

import { useCallback, useEffect, useState } from "react";

export interface BriefTemplate {
  id: string;
  name: string;
  description: string | null;
  sport: string | null;
  render_style: string | null;
  caption_style: string | null;
  pacing: string | null;
  hook_phrases: string[];
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface BriefTemplateCreate {
  name: string;
  description?: string;
  sport?: string;
  render_style?: string;
  caption_style?: string;
  pacing?: string;
  hook_phrases?: string[];
  tags?: string[];
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "include",
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function useBriefTemplates(sport?: string) {
  const [templates, setTemplates] = useState<BriefTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = sport ? `?sport=${encodeURIComponent(sport)}` : "";
      const data = await apiFetch<BriefTemplate[]>(`/api/brief-templates${params}`);
      setTemplates(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, [sport]);

  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (body: BriefTemplateCreate) => {
    const created = await apiFetch<BriefTemplate>("/api/brief-templates", {
      method: "POST",
      body: JSON.stringify(body),
    });
    setTemplates((prev) => [created, ...prev]);
    return created;
  }, []);

  const remove = useCallback(async (id: string) => {
    await apiFetch(`/api/brief-templates/${id}`, { method: "DELETE" });
    setTemplates((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { templates, loading, error, create, remove, reload: load };
}
