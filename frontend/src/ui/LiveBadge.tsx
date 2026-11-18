import { useT } from '@/i18n/useT';

export function LiveBadge({ className = '' }: { className?: string }) {
  const t = useT();
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border border-bull/40 bg-bull/10 px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-bull ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-bull" aria-hidden="true" />
      {t('common.liveMexc')}
    </span>
  );
}
