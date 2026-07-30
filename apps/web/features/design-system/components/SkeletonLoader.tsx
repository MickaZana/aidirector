import { cn } from "../utils/cn";

interface SkeletonLoaderProps {
  /** Number of skeleton lines to render */
  lines?: number;
  /** Optional className override */
  className?: string;
  /** Width of each line — single value applies to all, array applies per line */
  widths?: string | string[];
  /** Height of each line */
  height?: "sm" | "md" | "lg";
  /** Orientation */
  orientation?: "vertical" | "horizontal";
}

const HEIGHT_MAP = {
  sm: "h-3",
  md: "h-4",
  lg: "h-6",
} as const;

/**
 * SkeletonLoader — shimmer placeholder for content that is loading.
 *
 * Prevents layout shift by matching the dimensions of the expected content.
 * Uses `motion-safe:animate-pulse` so it doesn't pulse when users prefer
 * reduced motion.
 *
 * Usage:
 *   <SkeletonLoader lines={3} widths={["100%", "80%", "60%"]} />
 *   <SkeletonLoader lines={1} height="lg" className="w-full" />
 */
export function SkeletonLoader({
  lines = 1,
  className,
  widths = "100%",
  height = "md",
  orientation = "vertical",
}: SkeletonLoaderProps) {
  const widthsArray = Array.isArray(widths) ? widths : Array(lines).fill(widths);

  return (
    <div
      className={cn(
        "motion-safe:animate-pulse",
        orientation === "horizontal" && "flex items-center gap-3",
        className,
      )}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "rounded-lg bg-slate-200",
            HEIGHT_MAP[height],
            orientation === "vertical" && "mb-3 last:mb-0",
          )}
          style={{ width: widthsArray[i] ?? widthsArray[0] }}
        />
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  );
}
