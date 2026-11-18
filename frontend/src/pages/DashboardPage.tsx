import { Activity, Layers, Plug } from 'lucide-react';
import { useState } from 'react';
import { DEMO_METRICS } from '@/features/market/demoData';
import { MarketTable } from '@/features/market/MarketTable';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { DemoBadge, DemoBanner } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
import { LiveBadge } from '@/ui/LiveBadge';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';
import { fmtPrice } from '@/utils/format';

type Account = 'real' | 'paper';

export function DashboardPage() {
  const t = useT();
  const [account, setAccount] = useState<Account>('paper');
  const { rows, isLive } = useLiveMarkets();
  const m = DEMO_METRICS;
  const period = t('dash.vs24h');

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{t('dash.title')}</h2>
          {account === 'paper' && <DemoBadge />}
        </div>
        <Segmented<Account>
          ariaLabel={t('dash.title')}
          value={account}
          onChange={setAccount}
          options={[
            { value: 'real', label: t('dash.accountReal') },
            { value: 'paper', label: t('dash.accountPaper') },
          ]}
        />
      </div>

      {account === 'paper' ? (
        <>
          <DemoBanner />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <MetricCard demo label={t('dash.portfolio')} value={`${fmtPrice(m.portfolio.value)}`} deltaPct={m.portfolio.deltaPct} period={period} spark={m.portfolio.spark} tip={t('dash.tip.portfolio')} />
            <MetricCard demo label={t('dash.availableUsdt')} value={fmtPrice(m.availableUsdt.value)} tip={t('dash.tip.usdt')} spark={m.availableUsdt.spark} />
            <MetricCard demo label={t('dash.unrealized')} value={fmtPrice(m.unrealized.value)} deltaPct={m.unrealized.deltaPct} period={period} spark={m.unrealized.spark} tip={t('dash.tip.unrealized')} />
            <MetricCard demo label={t('dash.realized')} value={fmtPrice(m.realized.value)} deltaPct={m.realized.deltaPct} period={period} spark={m.realized.spark} tip={t('dash.tip.realized')} />
            <MetricCard demo label={t('dash.todayReturn')} value={`${m.todayReturn.value.toFixed(2)}%`} deltaPct={m.todayReturn.deltaPct} period={period} spark={m.todayReturn.spark} tip={t('dash.tip.today')} />
            <MetricCard demo label={t('dash.activeStrategies')} value={String(m.activeStrategies.value)} tip={t('dash.tip.strategies')} />
            <MetricCard demo label={t('dash.openPositions')} value={String(m.openPositions.value)} tip={t('dash.tip.positions')} />
          </div>
        </>
      ) : (
        <Panel>
          <EmptyState icon={Plug} title={t('dash.realEmptyTitle')} body={t('dash.realEmptyBody')} />
        </Panel>
      )}

      <Panel title={t('dash.markets')} actions={isLive ? <LiveBadge /> : <DemoBadge />}>
        <MarketTable rows={rows} />
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t('dash.strategiesTitle')}>
          <EmptyState icon={Layers} title={t('common.notBuilt')} body={t('dash.strategiesEmpty')} />
        </Panel>
        <Panel title={t('dash.activityTitle')}>
          <EmptyState icon={Activity} title={t('common.notBuilt')} body={t('dash.activityEmpty')} />
        </Panel>
      </div>
    </div>
  );
}
