import { useQuery } from '@tanstack/react-query';
import { TrendingUp } from 'lucide-react';
import { useState } from 'react';
import { useT } from '@/i18n/useT';
import { getBacktest, listBacktests } from '@/services/api';
import { EmptyState } from '@/ui/EmptyState';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { Sparkline } from '@/ui/Sparkline';

export function PerformancePage() {
  const t = useT();
  const { data, isLoading } = useQuery({ queryKey: ['backtests'], queryFn: listBacktests });
  const runs = data?.items ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const activeId = selectedId ?? runs[0]?.id ?? null;

  const { data: detail } = useQuery({
    queryKey: ['backtest-detail', activeId],
    queryFn: () => getBacktest(activeId!),
    enabled: Boolean(activeId),
  });

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex items-center gap-2">
        <TrendingUp className="h-5 w-5 text-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{t('bt.perfTitle')}</h2>
      </div>

      {isLoading ? (
        <p className="text-xs text-mute">{t('common.loading')}</p>
      ) : runs.length === 0 ? (
        <Panel>
          <EmptyState icon={TrendingUp} title={t('bt.historyTitle')} body="Run a backtest in the Backtesting Lab to inspect historical equity and drawdown curves." />
        </Panel>
      ) : (
        <>
          <Panel title={`${t('bt.historyTitle')} (${runs.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-start text-xs">
                <thead className="border-b border-line bg-surface text-mute">
                  <tr>
                    <th className="px-3 py-2 text-start">Strategy</th>
                    <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                    <th className="px-3 py-2 text-end">{t('bt.totalReturn')}</th>
                    <th className="px-3 py-2 text-end">{t('bt.winRate')}</th>
                    <th className="px-3 py-2 text-end">{t('bt.profitFactor')}</th>
                    <th className="px-3 py-2 text-end">{t('bt.maxDrawdown')}</th>
                    <th className="px-3 py-2 text-end">{t('bt.tradesCount')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {runs.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedId(r.id)}
                      className={`cursor-pointer hover:bg-surface/60 ${activeId === r.id ? 'bg-elevated' : ''}`}
                    >
                      <td className="px-3 py-2 font-semibold">{r.strategy_name} (v{r.version_no})</td>
                      <td className="num px-3 py-2">{r.symbol} · {r.timeframe}</td>
                      <td className={`num px-3 py-2 text-end font-medium ${r.total_return_pct >= 0 ? 'text-bull' : 'text-bear'}`}>
                        {r.total_return_pct.toFixed(2)}%
                      </td>
                      <td className="num px-3 py-2 text-end">{r.win_rate_pct.toFixed(1)}%</td>
                      <td className="num px-3 py-2 text-end">{r.profit_factor.toFixed(2)}</td>
                      <td className="num px-3 py-2 text-end text-bear">{r.max_drawdown_pct.toFixed(2)}%</td>
                      <td className="num px-3 py-2 text-end">{r.total_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {detail && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Panel title="Equity Curve">
                <div className="space-y-3 p-4">
                  <div className="grid grid-cols-3 gap-2">
                    <MetricCard label={t('bt.sharpe')} value={Number(detail.metrics.sharpe_ratio ?? 0).toFixed(2)} tip={t('bt.sharpe')} />
                    <MetricCard label={t('bt.sortino')} value={Number(detail.metrics.sortino_ratio ?? 0).toFixed(2)} tip={t('bt.sortino')} />
                    <MetricCard label={t('bt.expectancy')} value={`$${Number(detail.metrics.expectancy_usdt ?? 0).toFixed(2)}`} tip={t('bt.expectancy')} />
                  </div>
                  {(detail.metrics.equity_curve?.length ?? 0) >= 2 && (
                    <Sparkline
                      values={detail.metrics.equity_curve!.map((p) => p.equity)}
                      tone={Number(detail.metrics.total_return_pct ?? 0) >= 0 ? 'bull' : 'bear'}
                    />
                  )}
                </div>
              </Panel>
              <Panel title="Drawdown Curve (%)">
                <div className="p-4">
                  {(detail.metrics.drawdown_curve?.length ?? 0) >= 2 && (
                    <Sparkline
                      values={detail.metrics.drawdown_curve!.map((p) => p.drawdown_pct)}
                      tone="bear"
                    />
                  )}
                </div>
              </Panel>
            </div>
          )}
        </>
      )}
    </div>
  );
}
