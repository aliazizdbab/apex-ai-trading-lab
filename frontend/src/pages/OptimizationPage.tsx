import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertTriangle, Play, SlidersHorizontal } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { ApiError, listStrategies, optimizeBacktest } from '@/services/api';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';

export function OptimizationPage() {
  const t = useT();
  const { rows: markets } = useLiveMarkets();
  const { data: stratsData } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies });

  const strategies = stratsData?.items ?? [];
  const [selectedVerId, setSelectedVerId] = useState('');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [bars, setBars] = useState(300);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const effectiveVerId = selectedVerId || strategies[0]?.current_version_id || '';

  const optMut = useMutation({
    mutationFn: optimizeBacktest,
    onSuccess: () => setErrMsg(null),
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Walk-forward optimization failed'),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!effectiveVerId) return;
    optMut.mutate({
      strategy_version_id: effectiveVerId,
      symbol,
      timeframe,
      bars,
    });
  };

  const res = optMut.data;
  const inputCls =
    'min-h-[36px] w-full rounded border border-line bg-surface px-2.5 text-xs text-ink focus:border-cyan focus:outline-none';

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex items-center gap-2">
        <SlidersHorizontal className="h-5 w-5 text-cyan" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-semibold">{t('nav.optimization')}</h2>
          <p className="text-xs text-mute">
            Walk-Forward (70% In-Sample / 30% Out-of-Sample) parameter search & overfitting guard.
          </p>
        </div>
      </div>

      {errMsg && (
        <div className="rounded-md border border-bear/40 bg-bear/10 px-3 py-2 text-xs text-bear">{errMsg}</div>
      )}

      <Panel title={t('bt.optTitle')}>
        <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-6">
          <label className="col-span-2 text-xs text-mute">
            {t('strat.libraryTitle')}
            <select value={effectiveVerId} onChange={(e) => setSelectedVerId(e.target.value)} className={`${inputCls} mt-1`}>
              {strategies.map((s) => (
                <option key={s.id} value={s.current_version_id ?? ''}>
                  {s.name} (v{s.current_version?.version_no ?? 1})
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-mute">
            {t('mkt.pair')}
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={`${inputCls} mt-1`}>
              {markets.length > 0 ? (
                markets.slice(0, 40).map((m) => (
                  <option key={m.symbol} value={m.symbol}>
                    {m.symbol}
                  </option>
                ))
              ) : (
                <option value="BTC/USDT">BTC/USDT</option>
              )}
            </select>
          </label>
          <label className="text-xs text-mute">
            {t('term.timeframe')}
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={`${inputCls} mt-1`}>
              {TIMEFRAMES.map((tf) => (
                <option key={tf.id} value={tf.id}>
                  {tf.id}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-mute">
            {t('bt.bars')}
            <input
              type="number"
              min={120}
              max={1000}
              value={bars}
              onChange={(e) => setBars(Number(e.target.value))}
              className={`${inputCls} mt-1`}
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={!effectiveVerId || optMut.isPending}
              className="flex min-h-[36px] w-full items-center justify-center gap-1.5 rounded bg-cyan px-3 text-xs font-semibold text-base hover:bg-cyan/90 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
              {optMut.isPending ? 'Searching…' : t('bt.runOptimize')}
            </button>
          </div>
        </form>
      </Panel>

      {res && (
        <>
          {res.overfitting_warning && (
            <div className="flex items-start gap-2 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <div className="font-semibold">Overfitting Warning Detected</div>
                <div>{res.overfitting_reason}</div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard
              label="Best Stop Loss / Take Profit"
              value={`${res.best_params.stop_loss_pct}% / ${res.best_params.take_profit_pct}%`}
              tip="Winning parameter pair selected on the 70% In-Sample split"
            />
            <MetricCard
              label="In-Sample Return (70%)"
              value={`${res.in_sample_metrics.total_return_pct.toFixed(2)}%`}
              deltaPct={res.in_sample_metrics.total_return_pct}
              period={`${res.in_sample_bars} bars`}
              tip="Return achieved during parameter optimization window"
            />
            <MetricCard
              label="Out-of-Sample Return (30%)"
              value={`${res.out_of_sample_metrics.total_return_pct.toFixed(2)}%`}
              deltaPct={res.out_of_sample_metrics.total_return_pct}
              period={`${res.out_of_sample_bars} bars`}
              tip="Unseen forward validation return using best In-Sample params"
            />
            <MetricCard
              label="OOS Sharpe / Max DD"
              value={`${res.out_of_sample_metrics.sharpe_ratio.toFixed(2)} / ${res.out_of_sample_metrics.max_drawdown_pct.toFixed(2)}%`}
              tip="Out-of-sample risk-adjusted return and worst drawdown"
            />
          </div>

          <Panel
            title="Parameter Sensitivity Grid"
            actions={
              <span className="text-xs text-mute">
                Snapshot {res.data_snapshot_hash.slice(0, 16)} · Split bar #{res.split_index}
              </span>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-start text-xs">
                <thead className="border-b border-line bg-surface text-mute">
                  <tr>
                    <th className="px-3 py-2 text-end">Stop Loss %</th>
                    <th className="px-3 py-2 text-end">Take Profit %</th>
                    <th className="px-3 py-2 text-end">IS Return %</th>
                    <th className="px-3 py-2 text-end">IS Win Rate %</th>
                    <th className="px-3 py-2 text-end">IS Max DD %</th>
                    <th className="px-3 py-2 text-end">IS Trades</th>
                    <th className="px-3 py-2 text-end">Objective Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {res.sensitivity_grid.map((row, idx) => {
                    const isBest =
                      row.stop_loss_pct === res.best_params.stop_loss_pct &&
                      row.take_profit_pct === res.best_params.take_profit_pct;
                    return (
                      <tr key={`${row.stop_loss_pct}-${row.take_profit_pct}-${idx}`} className={isBest ? 'bg-cyan/5' : ''}>
                        <td className="num px-3 py-2 text-end font-medium">{row.stop_loss_pct.toFixed(1)}%</td>
                        <td className="num px-3 py-2 text-end font-medium">{row.take_profit_pct.toFixed(1)}%</td>
                        <td
                          className={`num px-3 py-2 text-end ${
                            row.is_return_pct >= 0 ? 'text-bull' : 'text-bear'
                          }`}
                        >
                          {row.is_return_pct.toFixed(2)}%
                        </td>
                        <td className="num px-3 py-2 text-end">{row.is_win_rate_pct.toFixed(1)}%</td>
                        <td className="num px-3 py-2 text-end text-bear">-{row.is_max_drawdown_pct.toFixed(2)}%</td>
                        <td className="num px-3 py-2 text-end">{row.is_trades}</td>
                        <td className="num px-3 py-2 text-end font-semibold text-cyan">{row.score.toFixed(3)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
