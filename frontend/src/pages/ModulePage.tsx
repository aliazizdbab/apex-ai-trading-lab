import type { NavItem } from '@/config/navigation';
import { useT } from '@/i18n/useT';
import { EmptyState } from '@/ui/EmptyState';
import { Panel } from '@/ui/Panel';

/** Honest placeholder for modules that are not built yet. It shows no data and simulates nothing. */
export function ModulePage({ item }: { item: NavItem }) {
  const t = useT();
  const Icon = item.icon;
  return (
    <div className="mx-auto max-w-3xl">
      <Panel>
        <EmptyState icon={Icon} title={t(item.labelKey)} body={t('common.notBuiltBody')}>
          <div className="mt-2 flex flex-wrap justify-center gap-2 text-[11px]">
            <span className="rounded border border-line bg-surface px-2 py-1 text-mute">{t('common.notBuilt')}</span>
            <span className="rounded border border-cyan/50 bg-cyan/10 px-2 py-1 text-cyan">{t('common.plannedPhase', { n: item.phase })}</span>
          </div>
        </EmptyState>
      </Panel>
    </div>
  );
}
