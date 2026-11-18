import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FlaskConical, Play } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { ApiError, listStrategies, runBacktest } from '@/services/api';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { Sparkline } from '@/ui/Sparkline';
import { fmtPrice } from '@/utils/format';

export function BacktestingPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();
  const { data: stratsData } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies });

  const strategies = stratsData?.items ?? [];
  const [selectedVerId, setSelectedVerId] = useState<string>('');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [bars, setBars] = useState(300);
  const [capital, setCapital] = useState(10000);
  const [feePct, setFeePct] = useState(0.1);
  const [slipPct, setSlipPct] = useState(0.05);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const effectiveVerId = selectedVerId || strategies[0]?.current_version_id || '';

  const btMut = useMutation({
    mutationFn: runBacktest,
    onSuccess: () => {
      setErrMsg(null);
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Backtest failed'),
  });

  const onRun = (e: FormEvent) => {
    e.preventDefault();
    if (!effectiveVerId) return;
    btMut.mutate({
      strategy_version_id: effectiveVerId,
      symbol,
      timeframe,
      bars,
      initial_capital_usdt: capital,
      position_size_pct: 95,
      fee_pct: feePct,
      slippage_pct: slipPct,
    });
  };

  const res = btMut.data;
  const inputCls =
    'min-h-[36px] w-full rounded border border-line bg-surface px-2.5 text-xs text-ink focus:border-cyan focus:outline-none';

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex items-center gap-2">
        <FlaskConical className="h-5 w-5 text-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{t('bt.title')}</h2>
      </div>

      <Panel title={t('bt.title')}>
        <form onSubmit={onRun} className="grid gap-3 p-4 sm:grid-cols-3 lg:grid-cols-6">
          <label className="space-y-1 text-xs sm:col-span-2">
            <span className="text-mute">{t('strat.libraryTitle')}</span>
            <select value={effectiveVerId} onChange={(e) => setSelectedVerId(e.target.value)} className={inputCls}>
              {strategies.map((s) =>
                s.current_version ? (
                  <option key={s.id} value={s.current_version.id}>
                    {s.name} (v{s.current_version.version_no})
                  </option>
                ) : null,
              )}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('mkt.pair')}</span>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputCls}>
              {markets.map((m) => (
                <option key={m.symbol} value={m.symbol}>{m.symbol}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('term.timeframe')}</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={inputCls}>
              {TIMEFRAMES.map((tf) => (
                <option key={tf.id} value={tf.id}>{tf.id}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('bt.bars')}</span>
            <input type="number" min={60} max={1500} value={bars} onChange={(e) => setBars(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('bt.capital')}</span>
            <input type="number" min={50} value={capital} onChange={(e) => setCapital(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('bt.fee')}</span>
            <input type="number" step="0.01" min={0} max={2} value={feePct} onChange={(e) => setFeePct(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('bt.slippage')}</span>
            <input type="number" step="0.01" min={0} max={2} value={slipPct} onChange={(e) => setSlipPct(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
          </label>
          <div className="flex items-end sm:col-span-2">
            <button
              type="submit"
              disabled={btMut.isPending || !effectiveVerId}
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90 disabled:opacity-50"
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              {btMut.isPending ? t('common.loading') : t('bt.run')}
            </button>
          </div>
        </form>
        {errMsg && <p className="border-t border-line px-4 py-2 text-xs text-bear">{errMsg}</p>}
      </Panel>

      {res && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {res.vectorized_parity && (
              <span className="rounded border border-bull/40 bg-bull/10 px-2.5 py-1 font-medium text-bull">
                {t('bt.parityOk')}
              </span>
            )}
            <span className="font-mono text-mute" dir="ltr">
              Snapshot: {res.data_snapshot_hash.slice(0, 14)} · Gaps: {res.quality.gap_count}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            <MetricCard label={t('bt.totalReturn')} value={`${res.metrics.total_return_pct.toFixed(2)}%`} deltaPct={res.metrics.total_return_pct} tip={t('bt.totalReturn')} />
            <MetricCard label={t('bt.winRate')} value={`${res.metrics.win_rate_pct.toFixed(1)}%`} tip={t('bt.winRate')} />
            <MetricCard label={t('bt.profitFactor')} value={res.metrics.profit_factor.toFixed(2)} tip={t('bt.profitFactor')} />
            <MetricCard label={t('bt.maxDrawdown')} value={`${res.metrics.max_drawdown_pct.toFixed(2)}%`} tip={t('bt.maxDrawdown')} />
            <MetricCard label={t('bt.sharpe')} value={res.metrics.sharpe_ratio.toFixed(2)} tip={t('bt.sharpe')} />
            <MetricCard label={t('bt.sortino')} value={res.metrics.sortino_ratio.toFixed(2)} tip={t('bt.sortino')} />
            <MetricCard label={t('bt.expectancy')} value={`$${res.metrics.expectancy_usdt.toFixed(2)}`} tip={t('bt.expectancy')} />
            <MetricCard label={t('bt.tradesCount')} value={String(res.metrics.total_trades)} tip={`${t('bt.slTiebreak')}: ${res.metrics.sl_tiebreak_exits}`} />
          </div>

          <Panel title="Equity Curve">
            <div className="p-4">
              <div className="mb-2 flex justify-between text-xs text-mute" dir="ltr">
                <span>Start: ${fmtPrice(res.metrics.initial_capital)}</span>
                <span>Final: ${fmtPrice(res.metrics.final_equity)}</span>
              </div>
              <Sparkline
                values={res.equity_curve.map((p) => p.equity)}
                tone={res.metrics.total_return_pct >= 0 ? 'bull' : 'bear'}
              />
            </div>
          </Panel>

          <Panel title={`Trades (${res.trades.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-start text-xs">
                <thead className="border-b border-line bg-surface text-mute">
                  <tr>
                    <th className="px-3 py-2 text-start">Entry Time</th>
                    <th className="px-3 py-2 text-end">Entry</th>
                    <th className="px-3 py-2 text-end">Exit</th>
                    <th className="px-3 py-2 text-end">PnL (USDT)</th>
                    <th className="px-3 py-2 text-end">PnL %</th>
                    <th className="px-3 py-2 text-start">Exit Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {res.trades.map((tr, i) => (
                    <tr key={i}>
                      <td className="num px-3 py-2 text-mute">{new Date(tr.entry_time * 1000).toLocaleString()}</td>
                      <td className="num px-3 py-2 text-end">{fmtPrice(tr.entry_price)}</td>
                      <td className="num px-3 py-2 text-end">{fmtPrice(tr.exit_price)}</td>
                      <td className={`num px-3 py-2 text-end font-medium ${tr.pnl_usdt >= 0 ? 'text-bull' : 'text-bear'}`}>
                        {tr.pnl_usdt.toFixed(2)}
                      </td>
                      <td className={`num px-3 py-2 text-end ${tr.pnl_pct >= 0 ? 'text-bull' : 'text-bear'}`}>
                        {tr.pnl_pct.toFixed(2)}%
                      </td>
                      <td className="px-3 py-2 font-mono text-mute">{tr.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
