/**
 * Display formatters. No business logic; pure functions consumed by
 * presentation components.
 */

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatSeconds(seconds: number | null | undefined): string {
  if (seconds == null || !isFinite(seconds)) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const rem = Math.round(seconds - minutes * 60);
  return `${minutes}m ${rem.toString().padStart(2, "0")}s`;
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value == null || !isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatScore(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return "—";
  return value.toFixed(3);
}

export function formatCents(cents: number | null | undefined): string {
  if (cents == null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function shortenHash(hash: string | null | undefined, chars = 10): string {
  if (!hash) return "—";
  if (hash.length <= chars * 2 + 1) return hash;
  return `${hash.slice(0, chars)}…${hash.slice(-4)}`;
}

export function shortenId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.split("-")[0] ?? id.slice(0, 8);
}
