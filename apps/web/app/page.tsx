import Link from "next/link";
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import {
  ArrowRight,
  Clapperboard,
  Sparkles,
  Zap,
  Check,
  Play,
  ChevronRight,
  BarChart3,
  Layers,
  Shield,
  Clock,
  Film,
  Target,
} from "lucide-react";
import { Button } from "@/design-system/Button";
import { Badge } from "@/design-system/Badge";

export const dynamic = "force-dynamic";

/* ── Mock UI components (pure CSS art, no images needed) ── */

function MockUploadUI() {
  return (
    <div
      className="relative w-full rounded-2xl overflow-hidden border border-[color:var(--color-border-strong)]"
      style={{ background: "var(--color-surface-1)", boxShadow: "0 0 0 1px rgba(255,255,255,0.04) inset, 0 40px 80px -20px rgba(0,0,0,0.8), 0 0 60px -20px rgba(0,230,161,0.12)" }}
    >
      {/* Window chrome */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[color:var(--color-border-soft)]" style={{ background: "var(--color-surface-0)" }}>
        <div className="flex gap-1.5">
          <div className="h-3 w-3 rounded-full" style={{ background: "#ff5f57" }} />
          <div className="h-3 w-3 rounded-full" style={{ background: "#ffbd2e" }} />
          <div className="h-3 w-3 rounded-full" style={{ background: "#28ca41" }} />
        </div>
        <div className="flex-1 mx-3">
          <div className="h-5 rounded-md flex items-center px-2.5 text-[10px]" style={{ background: "var(--color-surface-2)", color: "var(--color-text-tertiary)" }}>
            AI Director · Upload Studio
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className="p-5 space-y-4">
        {/* Upload zone */}
        <div
          className="rounded-xl border-2 border-dashed p-8 text-center"
          style={{ borderColor: "rgba(0,230,161,0.25)", background: "rgba(0,230,161,0.03)" }}
        >
          <div className="mx-auto h-10 w-10 rounded-xl flex items-center justify-center mb-3" style={{ background: "rgba(0,230,161,0.12)" }}>
            <Film className="h-5 w-5" style={{ color: "var(--color-accent-green)" }} />
          </div>
          <div className="text-xs font-medium" style={{ color: "var(--color-text-primary)" }}>Match footage · 4K H.264 · MKV / MP4</div>
          <div className="mt-1 text-[10px]" style={{ color: "var(--color-text-tertiary)" }}>Drag & drop or click to upload</div>
          <div className="mt-3 mx-auto h-1.5 w-32 rounded-full overflow-hidden" style={{ background: "var(--color-surface-3)" }}>
            <div className="h-full rounded-full animate-shimmer relative overflow-hidden w-3/4" style={{ background: "linear-gradient(90deg, var(--color-accent-green-dim), var(--color-accent-green))" }}>
              <div className="absolute inset-0" style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)", animation: "shimmer 2.5s ease-in-out infinite" }} />
            </div>
          </div>
          <div className="mt-1.5 text-[10px]" style={{ color: "var(--color-accent-green)" }}>78% · 2.4 GB of 3.1 GB</div>
        </div>

        {/* Pipeline status */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Ingested", status: "done", val: "3.1 GB" },
            { label: "CV Analysis", status: "running", val: "FI-1→7" },
            { label: "Ranking", status: "pending", val: "—" },
          ].map((s) => (
            <div key={s.label} className="rounded-lg p-3" style={{ background: "var(--color-surface-2)" }}>
              <div className="flex items-center gap-1.5 mb-1">
                <div
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background: s.status === "done" ? "var(--color-accent-green)" : s.status === "running" ? "var(--color-accent-blue)" : "var(--color-text-muted)",
                    boxShadow: s.status === "running" ? "0 0 6px var(--color-accent-blue)" : undefined,
                  }}
                />
                <span className="text-[9px] uppercase tracking-widest" style={{ color: "var(--color-text-tertiary)" }}>{s.status}</span>
              </div>
              <div className="text-[10px] font-medium" style={{ color: "var(--color-text-secondary)" }}>{s.label}</div>
              <div className="text-xs font-semibold mt-0.5" style={{ color: s.status === "done" ? "var(--color-accent-green)" : "var(--color-text-primary)" }}>{s.val}</div>
            </div>
          ))}
        </div>

        {/* Waveform */}
        <div className="rounded-lg p-3" style={{ background: "var(--color-surface-2)" }}>
          <div className="text-[9px] uppercase tracking-widest mb-2" style={{ color: "var(--color-text-tertiary)" }}>Audio · 90 min match</div>
          <div className="flex items-end gap-px h-10">
            {Array.from({ length: 64 }, (_, i) => {
              const h = Math.sin(i * 0.4) * 0.4 + Math.sin(i * 0.15) * 0.3 + 0.3;
              const active = i < 40;
              return (
                <div
                  key={i}
                  className="flex-1 rounded-sm"
                  style={{
                    height: `${Math.max(8, h * 100)}%`,
                    background: active ? "var(--color-accent-green)" : "var(--color-surface-3)",
                    opacity: active ? 0.7 + h * 0.3 : 1,
                  }}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function MockClipsUI() {
  const clips = [
    { score: 9.4, ts: "78:12", tag: "Goal", color: "var(--color-accent-green)" },
    { score: 8.7, ts: "23:41", tag: "Key pass", color: "var(--color-accent-blue)" },
    { score: 8.1, ts: "55:08", tag: "Save", color: "var(--color-accent-gold)" },
    { score: 7.9, ts: "12:34", tag: "Tackle", color: "var(--color-accent-blue)" },
    { score: 7.6, ts: "67:22", tag: "Sprint", color: "var(--color-accent-green)" },
    { score: 7.2, ts: "44:01", tag: "Header", color: "var(--color-accent-gold)" },
  ];

  return (
    <div
      className="relative w-full rounded-2xl overflow-hidden border border-[color:var(--color-border-strong)]"
      style={{ background: "var(--color-surface-1)", boxShadow: "0 0 0 1px rgba(255,255,255,0.04) inset, 0 40px 80px -20px rgba(0,0,0,0.8), 0 0 60px -20px rgba(61,169,252,0.12)" }}
    >
      {/* Chrome */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--color-border-soft)]" style={{ background: "var(--color-surface-0)" }}>
        <div className="flex gap-1.5">
          <div className="h-3 w-3 rounded-full" style={{ background: "#ff5f57" }} />
          <div className="h-3 w-3 rounded-full" style={{ background: "#ffbd2e" }} />
          <div className="h-3 w-3 rounded-full" style={{ background: "#28ca41" }} />
        </div>
        <div className="text-[10px] tracking-widest uppercase" style={{ color: "var(--color-text-tertiary)" }}>Ranked Clips · 6 of 24</div>
        <div className="text-[10px]" style={{ color: "var(--color-accent-green)" }}>Export all ↗</div>
      </div>

      <div className="p-4 space-y-2">
        {clips.map((c, i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5"
            style={{ background: i === 0 ? "rgba(0,230,161,0.07)" : "var(--color-surface-2)", border: i === 0 ? "1px solid rgba(0,230,161,0.2)" : "1px solid transparent" }}
          >
            {/* Rank */}
            <div className="text-xs font-bold w-5 text-center" style={{ color: i === 0 ? "var(--color-accent-green)" : "var(--color-text-muted)" }}>
              {i + 1}
            </div>

            {/* Thumbnail placeholder */}
            <div
              className="h-9 w-16 rounded flex-shrink-0 flex items-center justify-center"
              style={{ background: "var(--color-surface-3)", border: "1px solid var(--color-border-soft)" }}
            >
              <Play className="h-3 w-3" style={{ color: c.color }} />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded"
                  style={{ background: `${c.color}18`, color: c.color }}
                >
                  {c.tag}
                </span>
                <span className="text-[10px]" style={{ color: "var(--color-text-tertiary)" }}>{c.ts}</span>
              </div>
              <div className="mt-1 h-1 rounded-full overflow-hidden" style={{ background: "var(--color-surface-3)" }}>
                <div className="h-full rounded-full" style={{ width: `${c.score * 10}%`, background: `linear-gradient(90deg, ${c.color}99, ${c.color})` }} />
              </div>
            </div>

            {/* Score */}
            <div className="text-sm font-bold tabular-nums" style={{ color: c.color }}>{c.score}</div>

            {/* Export buttons */}
            <div className="flex gap-1">
              {["9:16", "1:1"].map((r) => (
                <div key={r} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface-3)", color: "var(--color-text-tertiary)" }}>
                  {r}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Pricing tiers ── */

const PLANS = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    tagline: "For individual creators getting started.",
    accent: "var(--color-text-secondary)",
    features: [
      "5 matches / month",
      "3 exports per match",
      "720p output",
      "Watermarked",
      "9:16 & 1:1 formats",
      "Community support",
    ],
    cta: "Get started free",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$49",
    period: "/ month",
    tagline: "For serious content teams shipping daily.",
    accent: "var(--color-accent-green)",
    badge: "Most popular",
    features: [
      "50 matches / month",
      "Unlimited exports",
      "1080p · no watermark",
      "All 3 aspect ratios",
      "Provenance signing",
      "Priority render queue",
      "Webhook notifications",
      "Email support",
    ],
    cta: "Start Pro trial",
    highlighted: true,
  },
  {
    name: "Studio",
    price: "$179",
    period: "/ month",
    tagline: "For broadcast teams and agencies.",
    accent: "var(--color-accent-blue)",
    features: [
      "Unlimited matches",
      "4K output",
      "5 team seats",
      "API access (REST)",
      "Custom brief templates",
      "C2PA provenance",
      "SLA 99.9% uptime",
      "Dedicated support",
    ],
    cta: "Contact sales",
    highlighted: false,
  },
];

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">

      {/* ── Cinematic background ── */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        {/* Deep black base */}
        <div className="absolute inset-0" style={{ background: "#02030a" }} />
        {/* Green top glow */}
        <div
          className="absolute inset-0"
          style={{ background: "radial-gradient(ellipse 70% 55% at 50% -5%, rgba(0,230,161,0.10) 0%, transparent 65%)" }}
        />
        {/* Blue bottom glow */}
        <div
          className="absolute inset-0"
          style={{ background: "radial-gradient(ellipse 80% 45% at 80% 110%, rgba(61,169,252,0.07) 0%, transparent 60%)" }}
        />
        {/* Subtle grid */}
        <div
          className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage: "linear-gradient(rgba(255,255,255,0.8) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.8) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
            maskImage: "radial-gradient(ellipse 80% 70% at 50% 0%, black 0%, transparent 75%)",
          }}
        />
        {/* Film grain overlay */}
        <div
          className="absolute inset-0 opacity-[0.015] mix-blend-overlay"
          style={{
            backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
            backgroundSize: "200px 200px",
          }}
        />
      </div>

      {/* ── Header ── */}
      <header className="sticky top-0 z-50 mx-auto max-w-7xl px-6 lg:px-10 py-4 flex items-center justify-between">
        <div
          className="absolute inset-0 -z-10 border-b"
          style={{ background: "rgba(2,3,10,0.72)", backdropFilter: "blur(20px)", borderColor: "rgba(255,255,255,0.05)" }}
        />
        <div className="flex items-center gap-2.5">
          <div
            className="relative h-8 w-8 rounded-lg"
            style={{ background: "linear-gradient(135deg, var(--color-accent-green), var(--color-accent-blue))", boxShadow: "0 0 20px -4px rgba(0,230,161,0.5)" }}
          >
            <div
              className="absolute inset-[1.5px] rounded-md flex items-center justify-center"
              style={{ background: "var(--color-surface-0)" }}
            >
              <Clapperboard className="h-4 w-4" style={{ color: "var(--color-accent-green)" }} strokeWidth={2.5} />
            </div>
          </div>
          <span className="font-semibold tracking-tight text-sm">AI Director</span>
          <Badge tone="muted" className="ml-1 hidden sm:inline-flex">v0.9 · sports</Badge>
        </div>

        <nav className="hidden md:flex items-center gap-6 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {["Features", "Pricing", "Docs"].map((item) => (
            <a key={item} href={`#${item.toLowerCase()}`} className="transition-colors hover:text-white">{item}</a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <SignedOut>
            <SignInButton mode="modal">
              <Button variant="ghost" size="sm">Sign in</Button>
            </SignInButton>
            <SignInButton mode="modal">
              <Button size="sm">
                Get started <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <Button asChild size="sm">
              <Link href={"/app/upload" as never}>
                Open Studio <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </SignedIn>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="mx-auto max-w-7xl px-6 lg:px-10 pt-24 pb-20">
        <div className="text-center max-w-4xl mx-auto">
          {/* Eyebrow */}
          <div
            className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-[10px] uppercase tracking-[0.2em] mb-8"
            style={{
              background: "rgba(0,230,161,0.08)",
              border: "1px solid rgba(0,230,161,0.2)",
              color: "var(--color-accent-green)",
            }}
          >
            <Sparkles className="h-3 w-3" />
            OmegaClips intelligence · trust-gradient feedback loop
          </div>

          {/* Headline */}
          <h1
            className="text-5xl sm:text-6xl md:text-[80px] font-semibold tracking-[-0.03em] leading-[0.92]"
            style={{ color: "var(--color-text-primary)" }}
          >
            Sports intelligence
            <br />
            becomes{" "}
            <span
              className="relative inline-block"
              style={{
                background: "linear-gradient(90deg, var(--color-accent-green) 0%, var(--color-accent-blue) 50%, var(--color-accent-green) 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              cinema.
            </span>
          </h1>

          {/* Sub */}
          <p className="mt-7 max-w-2xl mx-auto text-lg leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
            Drop a match. The Director Agent picks the moments, frames the cut,
            drives the renderer, and ships platform-ready variants — captioned,
            auto-cropped, deterministically scored, every step audit-trailed.
          </p>

          {/* CTAs */}
          <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
            <SignedOut>
              <SignInButton mode="modal">
                <Button size="lg">
                  <Zap className="h-4 w-4" />
                  Start free
                </Button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <Button asChild size="lg">
                <Link href={"/app/upload" as never}>
                  <Zap className="h-4 w-4" />
                  Open Studio
                </Link>
              </Button>
            </SignedIn>
            <a href="#pricing">
              <Button variant="secondary" size="lg">
                See pricing
              </Button>
            </a>
          </div>

          {/* Trust stats */}
          <div className="mt-12 flex items-center justify-center gap-8 flex-wrap">
            {[
              { val: "FI-1→13", label: "Intelligence layers" },
              { val: "<4 min", label: "Match to clips" },
              { val: "3 ratios", label: "9:16 · 1:1 · 16:9" },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-2xl font-bold tabular-nums" style={{ color: "var(--color-text-primary)" }}>{s.val}</div>
                <div className="text-[10px] uppercase tracking-widest mt-0.5" style={{ color: "var(--color-text-tertiary)" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Hero feature chips */}
        <div className="mt-14 grid sm:grid-cols-3 gap-3 max-w-3xl mx-auto">
          {[
            { icon: Target, title: "Structural ranking", body: "FI-1→FI-13 layered intelligence picks the moments that matter." },
            { icon: BarChart3, title: "Capped feedback", body: "Engagement assists; never overrides. Cap ±0.15, gate 0.30." },
            { icon: Film, title: "Cinematic exports", body: "9:16 / 1:1 / 16:9 with platform-correct bitrate, watermark, safe zones." },
          ].map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl p-4"
              style={{
                background: "rgba(11,13,17,0.7)",
                border: "1px solid var(--color-border-soft)",
                backdropFilter: "blur(12px)",
              }}
            >
              <Icon className="h-4 w-4 mb-2" style={{ color: "var(--color-accent-green)" }} />
              <div className="text-xs font-semibold mb-1" style={{ color: "var(--color-text-primary)" }}>{title}</div>
              <div className="text-xs leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>{body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Feature Section 1: Upload → Pipeline (image left, text right) ── */}
      <section id="features" className="mx-auto max-w-7xl px-6 lg:px-10 py-24">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Mock UI */}
          <div className="animate-float relative">
            {/* Glow behind the card */}
            <div
              className="absolute -inset-8 -z-10 rounded-3xl blur-3xl opacity-30"
              style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(0,230,161,0.3), transparent 70%)" }}
            />
            <MockUploadUI />
          </div>

          {/* Text */}
          <div className="lg:pl-8">
            <div
              className="inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] mb-5 px-3 py-1.5 rounded-full"
              style={{ background: "rgba(0,230,161,0.08)", border: "1px solid rgba(0,230,161,0.18)", color: "var(--color-accent-green)" }}
            >
              <Clock className="h-3 w-3" />
              Zero-setup pipeline
            </div>

            <h2
              className="text-4xl sm:text-5xl font-semibold tracking-tight leading-[1.05] mb-6"
              style={{ color: "var(--color-text-primary)" }}
            >
              Upload a match.
              <br />
              <span style={{ color: "var(--color-text-secondary)", fontWeight: 400 }}>The Director handles</span>
              <br />
              the rest.
            </h2>

            <p className="text-base leading-relaxed mb-8" style={{ color: "var(--color-text-secondary)" }}>
              Drop any H.264, HEVC, or ProRes file. The pipeline immediately extracts audio, runs 13 layers of football intelligence — goal detection, key-pass scoring, defensive action recognition — and hands structured candidates to the render queue.
            </p>

            <ul className="space-y-3">
              {[
                "Auto-detects match half boundaries and injury time",
                "Concurrent CV analysis + audio waveform extraction",
                "Progress streamed in real time via WebSocket",
                "Audit log of every decision, every score",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  <div
                    className="mt-0.5 h-5 w-5 rounded-full flex-shrink-0 flex items-center justify-center"
                    style={{ background: "rgba(0,230,161,0.12)", border: "1px solid rgba(0,230,161,0.25)" }}
                  >
                    <Check className="h-3 w-3" style={{ color: "var(--color-accent-green)" }} />
                  </div>
                  {item}
                </li>
              ))}
            </ul>

            <div className="mt-10">
              <SignedOut>
                <SignInButton mode="modal">
                  <Button variant="secondary">
                    Try a match <ChevronRight className="h-4 w-4" />
                  </Button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <Button asChild variant="secondary">
                  <Link href={"/app/upload" as never}>
                    Open Upload Studio <ChevronRight className="h-4 w-4" />
                  </Link>
                </Button>
              </SignedIn>
            </div>
          </div>
        </div>
      </section>

      {/* ── Feature Section 2: Ranked clips → Export (text left, image right) ── */}
      <section className="mx-auto max-w-7xl px-6 lg:px-10 py-24">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Text */}
          <div className="lg:pr-8 order-2 lg:order-1">
            <div
              className="inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] mb-5 px-3 py-1.5 rounded-full"
              style={{ background: "rgba(61,169,252,0.08)", border: "1px solid rgba(61,169,252,0.18)", color: "var(--color-accent-blue)" }}
            >
              <Layers className="h-3 w-3" />
              Platform-ready in minutes
            </div>

            <h2
              className="text-4xl sm:text-5xl font-semibold tracking-tight leading-[1.05] mb-6"
              style={{ color: "var(--color-text-primary)" }}
            >
              Ranked clips.
              <br />
              <span style={{ color: "var(--color-text-secondary)", fontWeight: 400 }}>Export to every</span>
              <br />
              platform at once.
            </h2>

            <p className="text-base leading-relaxed mb-8" style={{ color: "var(--color-text-secondary)" }}>
              Every candidate is deterministically scored by the trust-gradient engine. The Director frames the best 6–24 moments and queues renders for all three aspect ratios simultaneously — captions burned-in, safe zones respected, provenance signed.
            </p>

            <ul className="space-y-3">
              {[
                "Trust-gradient score: structural + feedback capped at ±0.15",
                "Auto title generation from match transcript",
                "SRT subtitles burned in via FFmpeg subtitles filter",
                "Ed25519 provenance manifest on every exported clip",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  <div
                    className="mt-0.5 h-5 w-5 rounded-full flex-shrink-0 flex items-center justify-center"
                    style={{ background: "rgba(61,169,252,0.12)", border: "1px solid rgba(61,169,252,0.25)" }}
                  >
                    <Check className="h-3 w-3" style={{ color: "var(--color-accent-blue)" }} />
                  </div>
                  {item}
                </li>
              ))}
            </ul>

            <div className="mt-10">
              <SignedOut>
                <SignInButton mode="modal">
                  <Button variant="secondary">
                    See the clips board <ChevronRight className="h-4 w-4" />
                  </Button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <Button asChild variant="secondary">
                  <Link href={"/app/clips" as never}>
                    Open Clips Board <ChevronRight className="h-4 w-4" />
                  </Link>
                </Button>
              </SignedIn>
            </div>
          </div>

          {/* Mock UI */}
          <div className="animate-float order-1 lg:order-2 relative" style={{ animationDelay: "1s" }}>
            <div
              className="absolute -inset-8 -z-10 rounded-3xl blur-3xl opacity-25"
              style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(61,169,252,0.35), transparent 70%)" }}
            />
            <MockClipsUI />
          </div>
        </div>
      </section>

      {/* ── Paywall / Pricing ── */}
      <section id="pricing" className="mx-auto max-w-7xl px-6 lg:px-10 py-24">
        {/* Section header */}
        <div className="text-center mb-16">
          <div
            className="inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] mb-5 px-3 py-1.5 rounded-full"
            style={{ background: "rgba(247,201,72,0.08)", border: "1px solid rgba(247,201,72,0.2)", color: "var(--color-accent-gold)" }}
          >
            <Shield className="h-3 w-3" />
            Simple, transparent pricing
          </div>
          <h2 className="text-4xl sm:text-5xl font-semibold tracking-tight" style={{ color: "var(--color-text-primary)" }}>
            Start free. Scale when you ship.
          </h2>
          <p className="mt-4 text-base max-w-xl mx-auto" style={{ color: "var(--color-text-secondary)" }}>
            No per-seat fees for individuals. Upgrade when you need more matches,
            higher resolution, or team collaboration.
          </p>
        </div>

        {/* Pricing cards */}
        <div className="grid lg:grid-cols-3 gap-6 items-start">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className="relative rounded-2xl p-7 flex flex-col"
              style={{
                background: plan.highlighted ? "rgba(0,230,161,0.04)" : "var(--color-surface-1)",
                border: plan.highlighted
                  ? "1px solid rgba(0,230,161,0.35)"
                  : "1px solid var(--color-border-soft)",
                boxShadow: plan.highlighted
                  ? "0 0 0 1px rgba(0,230,161,0.08) inset, 0 40px 80px -20px rgba(0,230,161,0.12)"
                  : "var(--shadow-card)",
              }}
            >
              {/* Popular badge */}
              {plan.badge && (
                <div
                  className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] uppercase tracking-[0.18em] px-3 py-1 rounded-full font-semibold"
                  style={{
                    background: "linear-gradient(90deg, var(--color-accent-green-dim), var(--color-accent-green))",
                    color: "var(--color-surface-0)",
                  }}
                >
                  {plan.badge}
                </div>
              )}

              {/* Plan name */}
              <div className="text-xs uppercase tracking-[0.18em] font-semibold mb-2" style={{ color: plan.accent }}>
                {plan.name}
              </div>

              {/* Price */}
              <div className="flex items-end gap-1 mb-1">
                <span className="text-5xl font-bold tracking-tight" style={{ color: "var(--color-text-primary)" }}>
                  {plan.price}
                </span>
                {plan.period && (
                  <span className="text-sm mb-1.5" style={{ color: "var(--color-text-tertiary)" }}>{plan.period}</span>
                )}
              </div>

              <p className="text-sm mb-7" style={{ color: "var(--color-text-secondary)" }}>{plan.tagline}</p>

              {/* Divider */}
              <div className="mb-7" style={{ height: "1px", background: "var(--color-border-soft)" }} />

              {/* Features */}
              <ul className="space-y-3 flex-1 mb-8">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-3 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                    <Check className="h-3.5 w-3.5 flex-shrink-0" style={{ color: plan.accent }} />
                    {f}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <SignedOut>
                <SignInButton mode="modal">
                  <button
                    className="w-full py-3 rounded-xl text-sm font-semibold transition-all"
                    style={
                      plan.highlighted
                        ? {
                            background: "linear-gradient(135deg, var(--color-accent-green-dim), var(--color-accent-green))",
                            color: "var(--color-surface-0)",
                            boxShadow: "0 0 24px -6px rgba(0,230,161,0.5)",
                          }
                        : {
                            background: "var(--color-surface-2)",
                            color: "var(--color-text-primary)",
                            border: "1px solid var(--color-border-strong)",
                          }
                    }
                  >
                    {plan.cta}
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <Link
                  href={"/app/upload" as never}
                  className="w-full py-3 rounded-xl text-sm font-semibold text-center block transition-all"
                  style={
                    plan.highlighted
                      ? {
                          background: "linear-gradient(135deg, var(--color-accent-green-dim), var(--color-accent-green))",
                          color: "var(--color-surface-0)",
                          boxShadow: "0 0 24px -6px rgba(0,230,161,0.5)",
                        }
                      : {
                          background: "var(--color-surface-2)",
                          color: "var(--color-text-primary)",
                          border: "1px solid var(--color-border-strong)",
                        }
                  }
                >
                  {plan.cta}
                </Link>
              </SignedIn>
            </div>
          ))}
        </div>

        {/* Enterprise note */}
        <p className="text-center mt-8 text-sm" style={{ color: "var(--color-text-tertiary)" }}>
          Need a custom contract, on-prem deploy, or compliance review?{" "}
          <a href="mailto:mike.mediainstitute@gmail.com" className="underline underline-offset-2 transition-colors" style={{ color: "var(--color-text-secondary)" }}>
            Talk to us.
          </a>
        </p>
      </section>

      {/* ── Bottom CTA banner ── */}
      <section className="mx-auto max-w-7xl px-6 lg:px-10 py-16">
        <div
          className="relative rounded-2xl px-10 py-14 text-center overflow-hidden"
          style={{
            background: "linear-gradient(135deg, rgba(0,230,161,0.07) 0%, rgba(61,169,252,0.05) 100%)",
            border: "1px solid rgba(0,230,161,0.18)",
          }}
        >
          {/* Background glow */}
          <div
            className="absolute inset-0 -z-10 blur-3xl opacity-40"
            style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(0,230,161,0.25), transparent 70%)" }}
          />
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight mb-4" style={{ color: "var(--color-text-primary)" }}>
            Ready to direct?
          </h2>
          <p className="text-base mb-8 max-w-lg mx-auto" style={{ color: "var(--color-text-secondary)" }}>
            Your first 5 matches are free. No credit card, no setup. Drop a file and the Director ships clips in under 4 minutes.
          </p>
          <SignedOut>
            <SignInButton mode="modal">
              <Button size="lg">
                <Zap className="h-4 w-4" />
                Get started free
              </Button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <Button asChild size="lg">
              <Link href={"/app/upload" as never}>
                <Zap className="h-4 w-4" />
                Open Studio
              </Link>
            </Button>
          </SignedIn>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer
        className="mx-auto max-w-7xl px-6 lg:px-10 pt-12 pb-10"
        style={{ borderTop: "1px solid var(--color-border-soft)" }}
      >
        {/* Top row */}
        <div className="flex flex-col sm:flex-row items-start justify-between gap-8 mb-10">
          {/* Brand */}
          <div className="max-w-xs">
            <div className="flex items-center gap-2.5 mb-3">
              <div
                className="h-7 w-7 rounded-md flex items-center justify-center"
                style={{ background: "linear-gradient(135deg, var(--color-accent-green), var(--color-accent-blue))", boxShadow: "0 0 16px -4px rgba(0,230,161,0.4)" }}
              >
                <Clapperboard className="h-4 w-4" style={{ color: "var(--color-surface-0)" }} strokeWidth={2.5} />
              </div>
              <span className="font-semibold text-sm" style={{ color: "var(--color-text-primary)" }}>AI Director</span>
            </div>
            <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-tertiary)" }}>
              Sports intelligence meets cinematic editing. Built on OmegaClips.
              A Micany subsidiary product.
            </p>
          </div>

          {/* Links */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-8 text-xs">
            <div>
              <div className="font-semibold mb-3 text-[10px] uppercase tracking-[0.15em]" style={{ color: "var(--color-text-tertiary)" }}>Product</div>
              <ul className="space-y-2">
                {["Features", "Pricing", "Docs"].map((l) => (
                  <li key={l}>
                    <a href={`#${l.toLowerCase()}`} className="footer-link">{l}</a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="font-semibold mb-3 text-[10px] uppercase tracking-[0.15em]" style={{ color: "var(--color-text-tertiary)" }}>Legal</div>
              <ul className="space-y-2">
                <li>
                  <Link href={"/terms" as never} className="footer-link">Terms of Use</Link>
                </li>
                <li>
                  <Link href={"/privacy" as never} className="footer-link">Privacy & GDPR</Link>
                </li>
              </ul>
            </div>
            <div>
              <div className="font-semibold mb-3 text-[10px] uppercase tracking-[0.15em]" style={{ color: "var(--color-text-tertiary)" }}>Company</div>
              <ul className="space-y-2">
                <li>
                  <a href="mailto:mike.mediainstitute@gmail.com" className="footer-link">Contact</a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom row */}
        <div
          className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-6 text-[10px] uppercase tracking-[0.15em]"
          style={{ borderTop: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }}
        >
          <span>© {new Date().getFullYear()} Micany · AI Director is a Micany subsidiary. All rights reserved.</span>
          <span>78fcd57 · Built on OmegaClips</span>
        </div>
      </footer>
    </main>
  );
}
