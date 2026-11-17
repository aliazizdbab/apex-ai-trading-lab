import { useT } from '@/i18n/useT';

export function DemoBadge() {
  const t = useT();
  return (
    <span className="inline-flex items-center rounded border border-amber/50 bg-amber/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber">
      {t('common.demo')}
    </span>
  );
}

export function DemoBanner() {
  const t = useT();
  return (
    <div role="note" className="flex items-start gap-2 rounded border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-amber">
      <DemoBadge />
      <span>{t('common.demoBanner')}</span>
    </div>
  );
}
