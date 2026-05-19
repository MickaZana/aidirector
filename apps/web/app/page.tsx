import Link from "next/link";
import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import { ArrowRight, Clapperboard, Sparkles, Zap } from "lucide-react";
import { Button } from "@/design-system/Button";
import { Badge } from "@/design-system/Badge";

/**
 * Cinematic landing page. Dark, glossy, broadcast-feel.
 * Designed to feel like a pro editing suite, not a SaaS dashboard.
 *
 * Dynamic because Clerk components can't be statically prerendered
 * without a publishable key. In production this is a no-op (a public
 * page); locally it lets `next build` succeed without secrets.
 */
export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Cinematic background field */}
      <div className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0 opacity-[0.18]"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 50% -10%, rgba(0, 230, 161, 0.5), transparent 60%), radial-gradient(ellipse 50% 40% at 80% 110%, rgba(61, 169, 252, 0.4), transparent 60%)",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
            maskImage: "radial-gradient(ellipse 60% 60% at 50% 50%, black 0%, transparent 80%)",
          }}
        />
      </div>

      {/* Top bar */}
      <header className="mx-auto max-w-7xl px-6 lg:px-10 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="relative h-8 w-8 rounded-lg bg-gradient-to-br from-[color:var(--color-accent-green)] to-[color:var(--color-accent-blue)] shadow-[0_0_24px_-4px_rgba(0,230,161,0.6)]">
            <div className="absolute inset-0.5 rounded-md bg-[color:var(--color-surface-0)] flex items-center justify-center">
              <Clapperboard className="h-4 w-4 text-[color:var(--color-accent-green)]" strokeWidth={2.5} />
            </div>
          </div>
          <span className="font-semibold tracking-tight">AI Director</span>
          <Badge tone="muted" className="ml-1">
            v0.9 · sports
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <SignedOut>
            <SignInButton mode="modal">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <Button asChild>
              <Link href={"/app/upload" as never}>
                Open Studio
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </SignedIn>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-6 lg:px-10 pt-20 pb-24 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)]/70 backdrop-blur-sm px-3.5 py-1.5 text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-secondary)] mb-8">
          <Sparkles className="h-3 w-3 text-[color:var(--color-accent-gold)]" />
          OmegaClips intelligence · trust-gradient feedback loop
        </div>

        <h1 className="text-5xl sm:text-6xl md:text-7xl font-semibold tracking-tight leading-[0.95]">
          Sports intelligence
          <br />
          becomes{" "}
          <span className="bg-gradient-to-r from-[color:var(--color-accent-green)] via-[color:var(--color-accent-blue)] to-[color:var(--color-accent-green)] bg-clip-text text-transparent">
            cinema.
          </span>
        </h1>

        <p className="mt-6 max-w-2xl mx-auto text-base sm:text-lg text-[color:var(--color-text-secondary)] leading-relaxed">
          Drop a match. The Director Agent picks the moments, frames the cut,
          drives the renderer, and ships platform-ready variants — captioned,
          auto-cropped, deterministically scored, every step audit-trailed.
        </p>

        <div className="mt-9 flex items-center justify-center gap-3 flex-wrap">
          <SignedOut>
            <SignInButton mode="modal">
              <Button size="lg">
                <Zap className="h-4 w-4" />
                Start a match
              </Button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <Button asChild size="lg">
              <Link href={"/app/upload" as never}>
                <Zap className="h-4 w-4" />
                Start a match
              </Link>
            </Button>
          </SignedIn>
          <Button variant="secondary" size="lg" asChild>
            <Link href={"/app/jobs" as never}>See a pipeline</Link>
          </Button>
        </div>

        <div className="mt-14 grid sm:grid-cols-3 gap-3 max-w-3xl mx-auto text-left">
          {[
            { title: "Structural ranking", body: "FI-1→FI-13 layered intelligence picks the moments that matter." },
            { title: "Capped feedback", body: "Engagement assists; never overrides. Cap ±0.15, gate 0.30." },
            { title: "Cinematic exports", body: "9:16 / 1:1 / 16:9 with platform-correct bitrate, watermark, safe zones." },
          ].map((b) => (
            <div
              key={b.title}
              className="rounded-xl border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)]/60 backdrop-blur-sm p-4"
            >
              <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-accent-green)]">
                {b.title}
              </div>
              <div className="mt-1.5 text-sm text-[color:var(--color-text-secondary)] leading-relaxed">
                {b.body}
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto max-w-7xl px-6 lg:px-10 pb-10 text-center text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
        Built on OmegaClips · 78fcd57
      </footer>
    </main>
  );
}
