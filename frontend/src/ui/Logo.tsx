export function Logo({ showText = true }: { showText?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-7 w-7 shrink-0" aria-hidden="true">
        <rect width="32" height="32" rx="6" className="fill-surface" />
        <path d="M16 5 27 27h-5l-6-12-6 12H5z" className="fill-cyan" />
        <path d="M11 22h10" className="stroke-surface" strokeWidth="2.5" />
      </svg>
      {showText && <span className="text-base font-semibold tracking-[0.18em]">APEX</span>}
    </span>
  );
}
