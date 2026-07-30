import Link from "next/link";

/**
 * Minimal footer — privacy, terms, support links, and version.
 */
export function Footer() {
  return (
    <footer className="border-t border-slate-200 pt-8 pb-12">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-400">
        <div className="flex items-center gap-6">
          <Link
            href="/privacy"
            className="hover:text-slate-600 transition-colors"
          >
            Privacy
          </Link>
          <Link
            href="/terms"
            className="hover:text-slate-600 transition-colors"
          >
            Terms
          </Link>
          <span className="hover:text-slate-600 transition-colors cursor-pointer">
            Support
          </span>
        </div>
        <span className="text-xs text-slate-300">v0.9</span>
      </div>
    </footer>
  );
}
