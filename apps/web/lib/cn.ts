import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Class-name helper. Use everywhere instead of raw template strings so
 * Tailwind class conflicts dedupe (e.g. `p-4 p-6` → `p-6`) and design
 * tokens stay deterministic.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
