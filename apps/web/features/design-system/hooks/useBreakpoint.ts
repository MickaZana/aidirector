"use client";

import { useState, useEffect } from "react";

type Breakpoint = "sm" | "md" | "lg" | "xl";

const BREAKPOINTS: Record<Breakpoint, number> = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
};

/**
 * Reactive breakpoint hook — returns which breakpoints are currently active.
 *
 * Uses `window.matchMedia` for performant, resize-friendly breakpoint detection.
 *
 * @example
 * const { isMd, isLg } = useBreakpoint();
 * if (isLg) { /* desktop layout *\/ }
 */
export function useBreakpoint() {
  const [matches, setMatches] = useState<Record<Breakpoint, boolean>>(() => {
    // Initialize on the server / first render
    if (typeof window === "undefined") {
      return { sm: false, md: false, lg: false, xl: false };
    }
    return {
      sm: window.innerWidth >= BREAKPOINTS.sm,
      md: window.innerWidth >= BREAKPOINTS.md,
      lg: window.innerWidth >= BREAKPOINTS.lg,
      xl: window.innerWidth >= BREAKPOINTS.xl,
    };
  });

  useEffect(() => {
    const mqls = Object.entries(BREAKPOINTS).map(([key, width]) => {
      const mql = window.matchMedia(`(min-width: ${width}px)`);
      const handler = (e: MediaQueryListEvent) => {
        setMatches((prev) => ({ ...prev, [key]: e.matches }));
      };
      mql.addEventListener("change", handler);
      return { mql, handler, key };
    });

    return () => {
      mqls.forEach(({ mql, handler }) =>
        mql.removeEventListener("change", handler),
      );
    };
  }, []);

  return matches;
}
