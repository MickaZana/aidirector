"use client";

import * as React from "react";
import { BookOpen, Plus, Trash2, ChevronRight, Tag, Zap } from "lucide-react";
import { TopBar } from "@/components/layout/TopBar";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { Button } from "@/design-system/Button";
import { useBriefTemplates, BriefTemplateCreate } from "@/hooks/useBriefTemplates";
import { cn } from "@/lib/cn";

const SPORT_OPTIONS = ["football", "basketball", "tennis", "rugby", "cricket"];
const STYLE_OPTIONS = ["ffmpeg_basic", "sports_hype", "documentary"];
const PACING_OPTIONS = ["fast", "medium", "slow"];
const CAPTION_OPTIONS = ["sports_hype", "minimal", "documentary"];

export default function TemplatesPage() {
  const { templates, loading, error, create, remove } = useBriefTemplates();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [showForm, setShowForm] = React.useState(false);
  const [deleting, setDeleting] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  const selectedTemplate = templates.find((t) => t.id === selected) ?? null;

  const [form, setForm] = React.useState<BriefTemplateCreate>({
    name: "",
    sport: "",
    render_style: "",
    caption_style: "",
    pacing: "",
    hook_phrases: [],
    tags: [],
  });
  const [hookInput, setHookInput] = React.useState("");
  const [tagInput, setTagInput] = React.useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const body: BriefTemplateCreate = {
        ...form,
        sport: form.sport || undefined,
        render_style: form.render_style || undefined,
        caption_style: form.caption_style || undefined,
        pacing: form.pacing || undefined,
      };
      const created = await create(body);
      setShowForm(false);
      setSelected(created.id);
      setForm({ name: "", sport: "", render_style: "", caption_style: "", pacing: "", hook_phrases: [], tags: [] });
      setHookInput("");
      setTagInput("");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await remove(id);
      if (selected === id) setSelected(null);
    } finally {
      setDeleting(null);
    }
  };

  const addHook = () => {
    const v = hookInput.trim();
    if (v && !form.hook_phrases?.includes(v)) {
      setForm((f) => ({ ...f, hook_phrases: [...(f.hook_phrases ?? []), v] }));
    }
    setHookInput("");
  };

  const addTag = () => {
    const v = tagInput.trim().toLowerCase();
    if (v && !form.tags?.includes(v)) {
      setForm((f) => ({ ...f, tags: [...(f.tags ?? []), v] }));
    }
    setTagInput("");
  };

  return (
    <>
      <TopBar
        title="Brief Templates"
        subtitle="Reusable director briefs — sport context, style, pacing, and hook phrases"
        trailing={
          <Button size="sm" onClick={() => { setShowForm(true); setSelected(null); }}>
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            New template
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-8 flex gap-6 h-[calc(100vh-4rem)] overflow-hidden">
        {/* ── List pane ── */}
        <div className="w-72 shrink-0 flex flex-col gap-3 overflow-y-auto">
          {loading && (
            <Surface variant="card" className="text-center py-10 text-sm text-[color:var(--color-text-tertiary)]">
              Loading…
            </Surface>
          )}
          {error && (
            <Surface variant="card" className="text-center py-10 text-sm text-[color:var(--color-accent-red)]">
              {error}
            </Surface>
          )}
          {!loading && !error && templates.length === 0 && (
            <Surface variant="card" className="text-center py-10">
              <BookOpen className="mx-auto h-8 w-8 text-[color:var(--color-text-tertiary)] mb-3" strokeWidth={1.5} />
              <p className="text-sm text-[color:var(--color-text-secondary)]">No templates yet</p>
              <p className="text-xs text-[color:var(--color-text-tertiary)] mt-1">
                Create one to save a reusable director brief.
              </p>
            </Surface>
          )}
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => { setSelected(t.id); setShowForm(false); }}
              className={cn(
                "w-full text-left rounded-xl border px-4 py-3 transition-colors",
                selected === t.id
                  ? "border-[color:var(--color-accent-green)] bg-[color:var(--color-surface-2)] shadow-[inset_0_0_0_1px_var(--color-border-accent)]"
                  : "border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)]/60 hover:bg-[color:var(--color-surface-2)]/60"
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium truncate">{t.name}</span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[color:var(--color-text-tertiary)]" />
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {t.sport && (
                  <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[color:var(--color-surface-3)] text-[color:var(--color-text-tertiary)]">
                    {t.sport}
                  </span>
                )}
                {t.pacing && (
                  <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[color:var(--color-surface-3)] text-[color:var(--color-text-tertiary)]">
                    {t.pacing}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* ── Detail / form pane ── */}
        <div className="flex-1 overflow-y-auto">
          {showForm && (
            <Surface variant="card" className="p-6 max-w-xl">
              <h2 className="text-base font-semibold mb-5">New brief template</h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <Field label="Name *">
                  <input
                    className={inputCls}
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="e.g. Premier League Highlights"
                    required
                  />
                </Field>

                <div className="grid grid-cols-2 gap-4">
                  <Field label="Sport">
                    <select className={inputCls} value={form.sport} onChange={(e) => setForm((f) => ({ ...f, sport: e.target.value }))}>
                      <option value="">— any —</option>
                      {SPORT_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </Field>
                  <Field label="Pacing">
                    <select className={inputCls} value={form.pacing} onChange={(e) => setForm((f) => ({ ...f, pacing: e.target.value }))}>
                      <option value="">— any —</option>
                      {PACING_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </Field>
                  <Field label="Render style">
                    <select className={inputCls} value={form.render_style} onChange={(e) => setForm((f) => ({ ...f, render_style: e.target.value }))}>
                      <option value="">— any —</option>
                      {STYLE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </Field>
                  <Field label="Caption style">
                    <select className={inputCls} value={form.caption_style} onChange={(e) => setForm((f) => ({ ...f, caption_style: e.target.value }))}>
                      <option value="">— any —</option>
                      {CAPTION_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </Field>
                </div>

                <Field label="Hook phrases">
                  <div className="flex gap-2">
                    <input className={cn(inputCls, "flex-1")} value={hookInput} onChange={(e) => setHookInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addHook())} placeholder="Type and press Enter" />
                    <button type="button" onClick={addHook} className="px-3 py-2 rounded-lg bg-[color:var(--color-surface-3)] text-sm hover:bg-[color:var(--color-surface-2)] transition-colors"><Plus className="h-3.5 w-3.5" /></button>
                  </div>
                  {(form.hook_phrases?.length ?? 0) > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {form.hook_phrases?.map((h) => (
                        <span key={h} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-[color:var(--color-accent-green)]/10 text-[color:var(--color-accent-green)] border border-[color:var(--color-accent-green)]/20">
                          <Zap className="h-2.5 w-2.5" />{h}
                          <button type="button" onClick={() => setForm((f) => ({ ...f, hook_phrases: f.hook_phrases?.filter((x) => x !== h) }))} className="ml-0.5 opacity-60 hover:opacity-100">×</button>
                        </span>
                      ))}
                    </div>
                  )}
                </Field>

                <Field label="Tags">
                  <div className="flex gap-2">
                    <input className={cn(inputCls, "flex-1")} value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())} placeholder="e.g. premier-league, highlight" />
                    <button type="button" onClick={addTag} className="px-3 py-2 rounded-lg bg-[color:var(--color-surface-3)] text-sm hover:bg-[color:var(--color-surface-2)] transition-colors"><Plus className="h-3.5 w-3.5" /></button>
                  </div>
                  {(form.tags?.length ?? 0) > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {form.tags?.map((t) => (
                        <span key={t} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-[color:var(--color-surface-3)] text-[color:var(--color-text-secondary)]">
                          <Tag className="h-2.5 w-2.5" />{t}
                          <button type="button" onClick={() => setForm((f) => ({ ...f, tags: f.tags?.filter((x) => x !== t) }))} className="ml-0.5 opacity-60 hover:opacity-100">×</button>
                        </span>
                      ))}
                    </div>
                  )}
                </Field>

                <div className="flex gap-3 pt-2">
                  <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Create template"}</Button>
                  <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
                </div>
              </form>
            </Surface>
          )}

          {!showForm && selectedTemplate && (
            <Surface variant="card" className="p-6 max-w-xl space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold">{selectedTemplate.name}</h2>
                  {selectedTemplate.description && (
                    <p className="text-sm text-[color:var(--color-text-secondary)] mt-1">{selectedTemplate.description}</p>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(selectedTemplate.id)}
                  disabled={deleting === selectedTemplate.id}
                  className="p-2 rounded-lg text-[color:var(--color-text-tertiary)] hover:text-[color:var(--color-accent-red)] hover:bg-[color:var(--color-accent-red)]/10 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="Sport" value={selectedTemplate.sport} />
                <Detail label="Pacing" value={selectedTemplate.pacing} />
                <Detail label="Render style" value={selectedTemplate.render_style} />
                <Detail label="Caption style" value={selectedTemplate.caption_style} />
              </div>

              {selectedTemplate.hook_phrases.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wider text-[color:var(--color-text-tertiary)] mb-2">Hook phrases</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTemplate.hook_phrases.map((h) => (
                      <span key={h} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-[color:var(--color-accent-green)]/10 text-[color:var(--color-accent-green)] border border-[color:var(--color-accent-green)]/20">
                        <Zap className="h-2.5 w-2.5" />{h}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedTemplate.tags.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wider text-[color:var(--color-text-tertiary)] mb-2">Tags</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTemplate.tags.map((t) => (
                      <span key={t} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-[color:var(--color-surface-3)] text-[color:var(--color-text-secondary)]">
                        <Tag className="h-2.5 w-2.5" />{t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-[10px] text-[color:var(--color-text-tertiary)]">
                Created {new Date(selectedTemplate.created_at).toLocaleDateString()}
              </p>
            </Surface>
          )}

          {!showForm && !selectedTemplate && !loading && (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <BookOpen className="h-10 w-10 text-[color:var(--color-text-tertiary)] mb-3" strokeWidth={1.5} />
              <p className="text-sm text-[color:var(--color-text-secondary)]">Select a template or create one</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ── Small helpers ──────────────────────────────────────────────────────────

const inputCls =
  "w-full rounded-lg bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] px-3 py-2 text-sm placeholder:text-[color:var(--color-text-tertiary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--color-accent-green)] transition-colors";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-[color:var(--color-text-secondary)] uppercase tracking-wider">
        {label}
      </label>
      {children}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)]">{label}</p>
      <p className="mt-0.5 font-medium">{value ?? <span className="text-[color:var(--color-text-tertiary)] font-normal">—</span>}</p>
    </div>
  );
}
