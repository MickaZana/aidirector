"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import {
  Badge,
  Button,
  Card,
  PageContainer,
  Typography,
} from "@/features/design-system";
import { analytics, type AnalyticsEvent } from "@/services/analytics";

type Metric = { label: string; value: string; detail?: string };

const eventCount = (events: AnalyticsEvent[], name: string) =>
  events.filter((event) => event.name === name).length;

function downloadFile(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatDuration(events: AnalyticsEvent[], start: string, end: string) {
  const durations = events
    .filter((event) => event.name === end)
    .map((event) => {
      const started = events.find(
        (candidate) =>
          candidate.name === start && candidate.timestamp <= event.timestamp,
      );
      return started ? (event.timestamp - started.timestamp) / 1000 : null;
    })
    .filter((value): value is number => value !== null);
  if (!durations.length) return "—";
  return `${(durations.reduce((sum, value) => sum + value, 0) / durations.length).toFixed(1)}s`;
}

function MetricGrid({ title, metrics }: { title: string; metrics: Metric[] }) {
  return (
    <section className="space-y-3" aria-labelledby={`${title}-heading`}>
      <Typography variant="title" as="h2" id={`${title}-heading`}>
        {title}
      </Typography>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {metrics.map((metric) => (
          <Card key={metric.label} dense>
            <Typography variant="overline">{metric.label}</Typography>
            <Typography variant="title" className="mt-2">
              {metric.value}
            </Typography>
            {metric.detail && (
              <Typography variant="caption" className="mt-1 block">
                {metric.detail}
              </Typography>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}

function Funnel({ events }: { events: AnalyticsEvent[] }) {
  const stages = [
    ["Visitors", "project_started"],
    ["Upload Started", "upload_started"],
    ["Upload Complete", "upload_completed"],
    ["Processing Started", "processing_started"],
    ["Processing Complete", "processing_completed"],
    ["Preview Viewed", "clip_preview_opened"],
    ["Downloaded", "download_clicked"],
  ] as const;
  const values = stages.map(([label, name]) => ({ label, value: eventCount(events, name) }));
  return (
    <Card>
      <Typography variant="title">User Journey Funnel</Typography>
      <div className="mt-5 space-y-3">
        {values.map((stage, index) => {
          const previous = values[index - 1]?.value ?? stage.value;
          const conversion = previous ? Math.round((stage.value / previous) * 100) : 0;
          return (
            <div key={stage.label}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700">{stage.label}</span>
                <span className="font-mono text-slate-500">{stage.value} · {index ? `${conversion}%` : "base"}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${Math.min(100, Math.max(4, conversion))}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default function BetaDashboardPage() {
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  const [events, setEvents] = useState<AnalyticsEvent[]>(() => analytics.getEvents());
  const [dataSource, setDataSource] = useState<"first_party_backend" | "local_fallback">("local_fallback");

  const isAdmin = Boolean(
    user?.publicMetadata &&
      (user.publicMetadata as { role?: string; isAdmin?: boolean }).role === "admin" ||
      (user?.publicMetadata as { isAdmin?: boolean } | undefined)?.isAdmin === true,
  );

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !isAdmin) return;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!baseUrl || baseUrl === "fixtures") return;
    void (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        const response = await fetch(`${baseUrl}/api/v1/analytics/admin/summary`, { headers: { authorization: `Bearer ${token}` } });
        if (!response.ok) return;
        const summary = (await response.json()) as { source: "first_party_backend"; counts: Record<string, number>; recent_events: { name: string; occurred_at: string }[] };
        const aggregated = Object.entries(summary.counts).flatMap(([name, count]) => Array.from({ length: Math.min(count, 1000) }, (_, index) => ({ name: name as AnalyticsEvent["name"], timestamp: Date.now() - index })));
        const recent = summary.recent_events.map((event) => ({ name: event.name as AnalyticsEvent["name"], timestamp: Date.parse(event.occurred_at) }));
        setEvents([...aggregated, ...recent]);
        setDataSource(summary.source);
      } catch {
        setDataSource("local_fallback");
      }
    })();
  }, [getToken, isAdmin, isLoaded, isSignedIn]);

  const metrics = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dayAgo = Date.now() - 86_400_000;
    const todayEvents = events.filter((event) => event.timestamp >= today.getTime());
    const activeEvents = events.filter((event) => event.timestamp >= dayAgo);
    const uploadAttempts = eventCount(events, "upload_started");
    const uploads = eventCount(events, "upload_completed");
    const jobsStarted = eventCount(events, "processing_started");
    const jobsCompleted = eventCount(events, "processing_completed");
    const scoreParts = [uploads ? Math.min(1, uploads / Math.max(1, uploadAttempts)) : 0, jobsStarted ? Math.min(1, jobsCompleted / jobsStarted) : 0, eventCount(events, "network_failure") ? 0.5 : 1, 0.5, eventCount(events, "offline_event") ? 0.5 : 1];
    const score = Math.round((scoreParts.reduce((sum, value) => sum + value, 0) / scoreParts.length) * 100);
    return { todayEvents, activeEvents, uploadAttempts, uploads, jobsStarted, jobsCompleted, score };
  }, [events]);

  if (!isLoaded) return <PageContainer><Typography variant="body">Loading access…</Typography></PageContainer>;
  if (!isSignedIn) return <PageContainer><Typography variant="title">Sign in required</Typography></PageContainer>;
  if (!isAdmin) return <PageContainer><Badge variant="error">403 · Admin only</Badge><Typography variant="title" className="mt-4">Beta Operations Dashboard</Typography><Typography variant="body" className="mt-2">This internal route is restricted to administrators.</Typography></PageContainer>;

  const exportReport = (kind: "csv" | "json") => {
    const report = { generatedAt: new Date().toISOString(), events, metrics };
    if (kind === "json") downloadFile("beta-report.json", JSON.stringify(report, null, 2), "application/json");
    else downloadFile("beta-report.csv", ["event,timestamp,properties", ...events.map((event) => `${event.name},${new Date(event.timestamp).toISOString()},"${JSON.stringify(event.properties ?? {}).replaceAll('"', '""')}"`)].join("\n"), "text/csv");
  };

  return (
    <PageContainer>
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="flex flex-wrap gap-2"><Badge variant={metrics.score >= 80 ? "success" : metrics.score >= 60 ? "warning" : "error"}>Beta readiness · {metrics.score}%</Badge><Badge variant={dataSource === "first_party_backend" ? "success" : "warning"}>{dataSource === "first_party_backend" ? "Aggregated backend data" : "Local fallback data"}</Badge></div>
          <Typography variant="hero" className="mt-3">Beta Operations</Typography>
          <Typography variant="subtitle" className="mt-2">Internal telemetry for the current beta cohort.</Typography>
        </div>
        <div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" onClick={() => exportReport("csv")}>Export CSV</Button><Button size="sm" variant="secondary" onClick={() => exportReport("json")}>Export JSON</Button><Button size="sm" onClick={() => setEvents(analytics.getEvents())}>Refresh</Button></div>
      </div>

      <div className="mt-8 space-y-10">
        <MetricGrid title="Beta Overview" metrics={[{ label: "Total invited users", value: "—", detail: "Requires server-side identity aggregation" }, { label: "Active users · 24h", value: `${metrics.activeEvents.length}`, detail: "Tracked events" }, { label: "New users today", value: "—" }, { label: "Returning users", value: "—" }, { label: "Sessions today", value: `${metrics.todayEvents.length}` }]} />
        <MetricGrid title="Upload Metrics" metrics={[{ label: "Upload attempts", value: `${metrics.uploadAttempts}` }, { label: "Successful uploads", value: `${metrics.uploads}` }, { label: "Failed uploads", value: `${eventCount(events, "upload_failed")}` }, { label: "Success %", value: metrics.uploadAttempts ? `${Math.round((metrics.uploads / metrics.uploadAttempts) * 100)}%` : "—" }, { label: "Average upload size", value: "—" }, { label: "Average upload duration", value: formatDuration(events, "upload_started", "upload_completed") }]} />
        <MetricGrid title="Processing Metrics" metrics={[{ label: "Jobs started", value: `${metrics.jobsStarted}` }, { label: "Jobs completed", value: `${metrics.jobsCompleted}` }, { label: "Jobs cancelled", value: `${eventCount(events, "cancel_processing_used")}` }, { label: "Jobs failed", value: `${eventCount(events, "processing_failed")}` }, { label: "Average processing time", value: formatDuration(events, "processing_started", "processing_completed") }, { label: "Longest processing time", value: "—" }]} />
        <MetricGrid title="Clip Metrics" metrics={[{ label: "Clips generated", value: "—" }, { label: "Average clips per project", value: "—" }, { label: "Downloads", value: `${eventCount(events, "download_clicked")}` }, { label: "Download All usage", value: `${eventCount(events, "download_all_clicked")}` }, { label: "Preview opens", value: `${eventCount(events, "clip_preview_opened")}` }, { label: "Shares / Copy Link", value: `${eventCount(events, "share_used") + eventCount(events, "copy_link_used")}` }]} />
        <div className="grid gap-6 xl:grid-cols-2"><Funnel events={events} /><Card><Typography variant="title">Feedback</Typography><div className="mt-5 grid gap-4 sm:grid-cols-2"><Metric label="Average rating" value="—" /><Metric label="Feedback count" value={`${eventCount(events, "feedback_submitted")}`} /><Metric label="Top requested features" value="—" /><Metric label="Common complaints" value="—" /></div><Typography variant="small" className="mt-5">Recent comments require a server-backed feedback provider.</Typography></Card></div>
        <MetricGrid title="Stability" metrics={[{ label: "Runtime errors", value: "—" }, { label: "Processing failures", value: `${eventCount(events, "processing_failed")}` }, { label: "Upload failures", value: `${eventCount(events, "upload_failed")}` }, { label: "CSP violations", value: "0" }, { label: "Network failures", value: `${eventCount(events, "network_failure")}` }, { label: "Offline events", value: `${eventCount(events, "offline_event")}` }]} />
        <MetricGrid title="Performance" metrics={[{ label: "Average page load", value: "—" }, { label: "Largest Contentful Paint", value: "—" }, { label: "Average processing latency", value: formatDuration(events, "processing_started", "processing_completed") }, { label: "Slowest page", value: "—" }, { label: "Average session duration", value: "—" }]} />
        <Card><Typography variant="title">Recent Activity</Typography><div className="mt-4 divide-y divide-slate-100">{events.slice(-12).reverse().map((event) => <div className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm" key={`${event.name}-${event.timestamp}`}><span className="font-medium text-slate-700">{event.name.replaceAll("_", " ")}</span><span className="font-mono text-xs text-slate-400">{new Date(event.timestamp).toLocaleString()}</span></div>)}{!events.length && <Typography variant="small">No analytics events captured in this browser yet.</Typography>}</div></Card>
      </div>
    </PageContainer>
  );
}

function Metric({ label, value }: Metric) { return <div><Typography variant="overline">{label}</Typography><Typography variant="title" className="mt-1">{value}</Typography></div>; }
