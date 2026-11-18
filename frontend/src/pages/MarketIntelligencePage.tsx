import { useQuery } from '@tanstack/react-query';
import { Compass, RefreshCw } from 'lucide-react';
import { useT } from '@/i18n/useT';
import { fetchMarketIntelligence } from '@/services/api';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { fmtPct, fmtPrice } from '@/utils/format';

export function MarketIntelligencePage() {
  const t = useT();
  const { data, isFetching, refetch } = useQuery({
    queryKey: ['market-intelligence'],
    queryFn: fetchMarketIntelligence,
    refetchInterval: 30_000,
  });

  const regime = data?.regime ?? 'Loading…';
  const breadth = data?.breadth_pct ?? 0;
  const avgChange = data?.avg_change_pct ?? 0;

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-cyan" aria-hidden="true" />
          <h2 className="text-lg font-semibold">{t('ai.intelTitle')}</h2>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs text-ink hover:border-cyan/60"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MetricCard
          label={t('ai.regime')}
          value={regime}
          tip="Detected broad MEXC market regime based on breadth and average 24h momentum"
        />
        <MetricCard
          label={t('ai.breadth')}
          value={`${breadth.toFixed(1)}%`}
          tip="Percentage of tracked MEXC pairs with positive 24h performance"
        />
        <MetricCard
          label={t('ai.avgChange')}
          value={fmtPct(avgChange)}
          deltaPct={avgChange}
          tip="Mean 24h price change across tracked USDT pairs"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title={t('ai.volLeaders')} actions={<span className="text-xs text-mute">Intraday 24h High/Low Range %</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-end">{t('mkt.last')}</th>
                  <th className="px-3 py-2 text-end">24h Range %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {(data?.volatility_leaders ?? []).map((row) => (
                  <tr key={row.symbol}>
                    <td className="num px-3 py-2 font-semibold">{row.symbol}</td>
                    <td className="num px-3 py-2 text-end">{fmtPrice(row.last)}</td>
                    <td className="num px-3 py-2 text-end font-medium text-cyan">{row.range_pct.toFixed(2)}%</td>
                  </tr>
                ))}
                {(data?.volatility_leaders ?? []).length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-mute">
                      No market telemetry available yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title={t('ai.momLeaders')} actions={<span className="text-xs text-mute">Top 24h Movers</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-end">{t('mkt.last')}</th>
                  <th className="px-3 py-2 text-end">{t('mkt.change')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {(data?.momentum_leaders ?? []).map((row) => (
                  <tr key={row.symbol}>
                    <td className="num px-3 py-2 font-semibold">{row.symbol}</td>
                    <td className="num px-3 py-2 text-end">{fmtPrice(row.last)}</td>
                    <td
                      className={`num px-3 py-2 text-end font-medium ${
                        row.change24h >= 0 ? 'text-bull' : 'text-bear'
                      }`}
                    >
                      {fmtPct(row.change24h)}
                    </td>
                  </tr>
                ))}
                {(data?.momentum_leaders ?? []).length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-mute">
                      No market telemetry available yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
