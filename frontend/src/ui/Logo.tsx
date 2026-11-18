export function Logo({ showText = true }: { showText?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 64 64" className="h-7 w-7 shrink-0" aria-hidden="true">
        <defs>
          <linearGradient id="apex-logo-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#36C5F0" />
            <stop offset="100%" stopColor="#19C995" />
          </linearGradient>
        </defs>
        <rect width="64" height="64" rx="14" className="fill-surface" />
        <rect x="2" y="2" width="60" height="60" rx="12" fill="none" className="stroke-line" strokeWidth="2" />
        <path d="M32 11 53 51h-9.5L32 28.5 20.5 51H11z" fill="url(#apex-logo-grad)" />
        <rect x="22" y="38" width="20" height="5" rx="2.5" className="fill-surface" />
        <circle cx="49" cy="15" r="4" className="fill-emerald" />
      </svg>
      {showText && <span className="text-base font-semibold tracking-[0.18em]">APEX</span>}
    </span>
  );
}
