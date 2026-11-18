import { Globe } from 'lucide-react';
import { MarketTable } from '@/features/market/MarketTable';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { DemoBadge } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
import { LiveBadge } from '@/ui/LiveBadge';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { fmtCompact, fmtPrice } from '@/utils/format';

export function MarketOverviewPage() {
  const t = useT();
  const { rows, isLive, isError } = useLiveMarkets();

  const advancers = rows.filter((r) => r.change24h >= 0).length;
  const decliners = rows.length - advancers;
  const totalVol = rows.reduce((acc, r) => acc + r.volume24h, 0);
  const sortedByChange = [...rows].sort((a, b) => b.change24h - a.change24h);
  const topGainer = sortedByChange[0];
  const topLoser = sortedByChange[sortedByChange.length - 1];

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{t('mktOverview.title')}</h2>
          {isLive ? <LiveBadge /> : <DemoBadge />}
        </div>
      </div>

      {isError && !isLive ? (
        <Panel>
          <EmptyState icon={Globe} title={t('common.notConnected')} body={t('mktOverview.offline')} />
        </Panel>
      ) : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <MetricCard label={t('mktOverview.trackedPairs')} value={String(rows.length)} tip={t('mktOverview.trackedPairs')} />
        <MetricCard
          label={t('mktOverview.advancersDecliners')}
          value={`${advancers} / ${decliners}`}
          tip={t('mktOverview.advancersDecliners')}
        />
        <MetricCard label={t('mktOverview.totalVolume')} value={`$${fmtCompact(totalVol)}`} tip={t('mktOverview.totalVolume')} />
        {topGainer && (
          <MetricCard
            label={t('mktOverview.topGainer')}
            value={`${topGainer.symbol} (${fmtPrice(topGainer.last)})`}
            deltaPct={topGainer.change24h}
            period={t('dash.vs24h')}
            tip={t('mktOverview.topGainer')}
          />
        )}
        {topLoser && (
          <MetricCard
            label={t('mktOverview.topLoser')}
            value={`${topLoser.symbol} (${fmtPrice(topLoser.last)})`}
            deltaPct={topLoser.change24h}
            period={t('dash.vs24h')}
            tip={t('mktOverview.topLoser')}
          />
        )}
      </div>

      <Panel title={t('dash.markets')} actions={isLive ? <LiveBadge /> : <DemoBadge />}>
        <MarketTable rows={rows} />
      </Panel>
    </div>
  );
}
