"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api/runtime";
import type { BriefTemplate, BriefTemplateCreate } from "@/lib/api/types";

export type { BriefTemplate, BriefTemplateCreate };

export function useBriefTemplates(sport?: string) {
  const { endpoints, mode } = useApi();
  const [templates, setTemplates] = useState<BriefTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    if (!endpoints) {
      // Fixture mode — return empty set gracefully
      setTemplates([]);
      setLoading(false);
      return;
    }

    try {
      const data = await endpoints.listBriefTemplates(sport);
      setTemplates(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, [endpoints, sport]);

  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (body: BriefTemplateCreate) => {
    if (!endpoints) throw new Error("API not available in fixture mode");
    const created = await endpoints.createBriefTemplate(body);
    setTemplates((prev) => [created, ...prev]);
    return created;
  }, [endpoints]);

  const remove = useCallback(async (id: string) => {
    if (!endpoints) throw new Error("API not available in fixture mode");
    await endpoints.deleteBriefTemplate(id);
    setTemplates((prev) => prev.filter((t) => t.id !== id));
  }, [endpoints]);

  return { templates, loading, error, create, remove, reload: load };
}
