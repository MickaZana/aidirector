import Link from "next/link";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <header className="flex items-center justify-between mb-16">
        <h1 className="text-xl font-semibold tracking-tight">AI Director Agent</h1>
        <SignedIn>
          <UserButton />
        </SignedIn>
        <SignedOut>
          <SignInButton mode="modal" />
        </SignedOut>
      </header>

      <section className="space-y-6">
        <h2 className="text-4xl font-semibold tracking-tight">
          Autonomous AI Director for short-form video.
        </h2>
        <p className="text-neutral-400 text-lg leading-relaxed">
          Upload a match. The Director Agent decides what becomes a clip, how it's framed,
          and which renderer produces it — captioned, auto-cropped, platform-ready in minutes.
        </p>
        <SignedIn>
          <Link
            href="/dashboard"
            className="inline-block rounded-md bg-white text-black px-5 py-2.5 font-medium"
          >
            Go to dashboard →
          </Link>
        </SignedIn>
      </section>
    </main>
  );
}
