import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ClipboardList, RotateCcw } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  fetchPaperOverview,
  resetPaperAccount,
  submitPaperOrder,
} from '@/services/api';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { fmtPrice } from '@/utils/format';

export function PaperTradingPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows: markets } = useLiveMarkets();
  const { data } = useQuery({
    queryKey: ['paper-overview'],
    queryFn: fetchPaperOverview,
    refetchInterval: 10_000,
  });

  const [symbol, setSymbol] = useState('BTC/USDT');
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [qty, setQty] = useState(0.02);
  const [slPct, setSlPct] = useState(1.5);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const orderMut = useMutation({
    mutationFn: submitPaperOrder,
    onSuccess: () => {
      setErrMsg(null);
      queryClient.invalidateQueries({ queryKey: ['paper-overview'] });
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Order failed'),
  });

  const resetMut = useMutation({
    mutationFn: resetPaperAccount,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['paper-overview'] }),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    orderMut.mutate({ symbol, side, order_type: 'MARKET', qty, stop_loss_pct: slPct });
  };

  const acc = data?.account;

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-cyan" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">{t('paper.title')}</h2>
            <p className="text-xs text-mute">{t('paper.subtitle')}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => resetMut.mutate()}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs hover:border-amber"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          {t('paper.reset')}
        </button>
      </div>

      {acc && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <MetricCard label={t('dash.portfolio')} value={`$${fmtPrice(acc.total_equity_usdt)}`} tip={t('dash.tip.portfolio')} />
          <MetricCard label={t('dash.availableUsdt')} value={`$${fmtPrice(acc.available_usdt)}`} tip={t('dash.tip.usdt')} />
          <MetricCard label={t('dash.unrealized')} value={`$${acc.unrealized_pnl_usdt.toFixed(2)}`} deltaPct={acc.unrealized_pnl_usdt} tip={t('dash.tip.unrealized')} />
          <MetricCard label={t('dash.realized')} value={`$${acc.realized_pnl_usdt.toFixed(2)}`} deltaPct={acc.realized_pnl_usdt} tip={t('dash.tip.realized')} />
          <MetricCard label={t('dash.openPositions')} value={String(data?.positions.length ?? 0)} tip={t('dash.tip.positions')} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Panel title={t('paper.submitOrder')}>
          <form onSubmit={onSubmit} className="space-y-3 p-4 text-xs">
            <label className="block space-y-1">
              <span className="text-mute">{t('mkt.pair')}</span>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5">
                {markets.map((m) => (
                  <option key={m.symbol} value={m.symbol}>{m.symbol} ({fmtPrice(m.last)})</option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button type="button" onClick={() => setSide('buy')} className={`min-h-[36px] rounded font-medium ${side === 'buy' ? 'bg-bull text-bg' : 'border border-line bg-surface text-mute'}`}>
                BUY
              </button>
              <button type="button" onClick={() => setSide('sell')} className={`min-h-[36px] rounded font-medium ${side === 'sell' ? 'bg-bear text-bg' : 'border border-line bg-surface text-mute'}`}>
                SELL
              </button>
            </div>
            <label className="block space-y-1">
              <span className="text-mute">Quantity</span>
              <input type="number" step="0.0001" min={0.0001} value={qty} onChange={(e) => setQty(Number(e.target.value))} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5 tabular-nums" />
            </label>
            <label className="block space-y-1">
              <span className="text-mute">{t('strat.stopLoss')}</span>
              <input type="number" step="0.1" min={0.1} value={slPct} onChange={(e) => setSlPct(Number(e.target.value))} className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5 tabular-nums" />
            </label>
            {errMsg && <p className="text-bear">{errMsg}</p>}
            <button type="submit" disabled={orderMut.isPending} className="min-h-[38px] w-full rounded bg-cyan font-medium text-bg hover:opacity-90">
              {t('paper.submitOrder')}
            </button>
          </form>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel title={`${t('nav.positions')} (${data?.positions.length ?? 0})`}>
            {(data?.positions ?? []).length === 0 ? (
              <p className="p-4 text-xs text-mute">No open paper positions.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-start text-xs">
                  <thead className="border-b border-line bg-surface text-mute">
                    <tr>
                      <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                      <th className="px-3 py-2 text-end">Qty</th>
                      <th className="px-3 py-2 text-end">Entry</th>
                      <th className="px-3 py-2 text-end">Mark</th>
                      <th className="px-3 py-2 text-end">Unrealized PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data!.positions.map((p) => (
                      <tr key={p.symbol}>
                        <td className="num px-3 py-2 font-semibold">{p.symbol}</td>
                        <td className="num px-3 py-2 text-end">{p.qty.toFixed(6)}</td>
                        <td className="num px-3 py-2 text-end">{fmtPrice(p.avg_entry_price)}</td>
                        <td className="num px-3 py-2 text-end">{fmtPrice(p.mark_price)}</td>
                        <td className={`num px-3 py-2 text-end font-medium ${p.unrealized_pnl_usdt >= 0 ? 'text-bull' : 'text-bear'}`}>
                          ${p.unrealized_pnl_usdt.toFixed(2)} ({p.unrealized_pnl_pct.toFixed(2)}%)
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title={`${t('nav.orders')} (${data?.orders.length ?? 0})`}>
            {(data?.orders ?? []).length === 0 ? (
              <p className="p-4 text-xs text-mute">No paper orders yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-start text-xs">
                  <thead className="border-b border-line bg-surface text-mute">
                    <tr>
                      <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                      <th className="px-3 py-2 text-start">Side</th>
                      <th className="px-3 py-2 text-end">Qty</th>
                      <th className="px-3 py-2 text-end">Price</th>
                      <th className="px-3 py-2 text-start">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data!.orders.slice(0, 12).map((o) => (
                      <tr key={o.id}>
                        <td className="num px-3 py-2 font-semibold">{o.symbol}</td>
                        <td className={`px-3 py-2 uppercase ${o.side === 'buy' ? 'text-bull' : 'text-bear'}`}>{o.side}</td>
                        <td className="num px-3 py-2 text-end">{o.qty}</td>
                        <td className="num px-3 py-2 text-end">{o.price ? fmtPrice(o.price) : '—'}</td>
                        <td className="px-3 py-2 font-mono text-mute">{o.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
