import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Director — Sports-tech AI for short-form video",
  description:
    "Autonomous AI Director for short-form sports video. Cinematic editing at compute speed.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: "#00e6a1",
          colorBackground: "#0b0d11",
          colorText: "#f5f7fa",
          colorInputBackground: "#11151b",
          colorInputText: "#f5f7fa",
        },
        elements: {
          card: "bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)]",
        },
      }}
    >
      <html lang="en">
        <body>
          {children}
          {/* Global overlay components — always mounted */}
          <Sprint45Overlays />
        </body>
      </html>
    </ClerkProvider>
  );
}

/**
 * Sprint 4.5 global overlay components.
 * Rendered outside the page tree so they stack above everything.
 */
import { Toaster } from "@/components/ui/Toaster";
import { RateLimitListener } from "@/components/error-handling/RateLimitListener";
import { BillingLimitListener } from "@/components/error-handling/BillingLimitListener";

function Sprint45Overlays() {
  return (
    <>
      <RateLimitListener />
      <BillingLimitListener />
      <Toaster />
    </>
  );
}
