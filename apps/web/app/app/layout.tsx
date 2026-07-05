import * as React from "react";
import { AppShell } from "@/components/layout/AppShell";
import { OfflineBanner } from "@/components/error-handling/OfflineBanner";

/**
 * Authenticated app shell. Sidebar + content. Each route owns its own
 * TopBar so it can carry route-specific trailing actions.
 *
 * All /app/* pages are dynamic — they read live job/upload state and
 * use Clerk's <UserButton> which can't be statically prerendered.
 */
export const dynamic = "force-dynamic";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <OfflineBanner />
      <AppShell>{children}</AppShell>
    </>
  );
}
