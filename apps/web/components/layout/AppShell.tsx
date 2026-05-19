import * as React from "react";
import { Sidebar } from "./Sidebar";

/**
 * Authenticated app shell — sidebar + main content. The top bar lives
 * inside each route so it can carry route-specific trailing content.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 relative z-10">{children}</main>
    </div>
  );
}
