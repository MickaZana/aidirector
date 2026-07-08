/**
 * Icon mark: rounded dark tile + shield crest + play-triangle + football-lace
 * seam — same composition as app/icon.svg (the favicon) and public/logo.svg,
 * kept as one inline component so nav/sidebar/footer stay in sync with the
 * favicon by construction rather than by copy-pasted markup.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="logoMarkGrad" x1="4" y1="54" x2="56" y2="10" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#00e6a1" />
          <stop offset="100%" stopColor="#3da9fc" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="14" fill="#0b0d11" />
      <path
        d="M32 9 L49 15.5 L49 33.5 C49 45 41.5 50.5 32 55 C22.5 50.5 15 45 15 33.5 L15 15.5 Z"
        fill="#11151b"
        stroke="url(#logoMarkGrad)"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path
        d="M25 24 Q22.5 32 25 41"
        stroke="#f7c948"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />
      <line x1="22.4" y1="27" x2="27.2" y2="27" stroke="#f7c948" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="22" y1="32" x2="27.4" y2="32" stroke="#f7c948" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="22.4" y1="37" x2="27.2" y2="37" stroke="#f7c948" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M28 21 L28 46 L47 33.5 Z" fill="url(#logoMarkGrad)" />
    </svg>
  );
}
