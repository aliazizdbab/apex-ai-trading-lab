import { useMutation } from '@tanstack/react-query';
import { FastForward, Play, Rewind, StepForward } from 'lucide-react';
import { useState } from 'react';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { TradingChart } from '@/features/chart/TradingChart';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  placeReplayOrder,
  startReplaySession,
  stepReplaySession,
  type ReplayViewResponse,
} from '@/services/api';
import { useUiStore } from '@/stores/uiStore';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { fmtPrice } from '@/utils/format';

export function ReplayPage() {
  const t = useT();
  const theme = useUiStore((s) => s.theme);
  const { rows: markets } = useLiveMarkets();

  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [orderQty, setOrderQty] = useState(0.05);
  const [session, setSession] = useState<ReplayViewResponse | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const startMut = useMutation({
    mutationFn: startReplaySession,
    onSuccess: (res) => {
      setErrMsg(null);
      setSession(res);
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Failed to start replay'),
  });

  const stepMut = useMutation({
    mutationFn: ({ id, steps }: { id: string; steps: number }) => stepReplaySession(id, steps),
    onSuccess: (res) => {
      setErrMsg(null);
      setSession(res);
    },
  });

  const orderMut = useMutation({
    mutationFn: ({ id, side, qty }: { id: string; side: 'buy' | 'sell'; qty: number }) =>
      placeReplayOrder(id, { side, qty }),
    onSuccess: (res) => {
      setErrMsg(null);
      setSession(res);
    },
    onError: (err) => setErrMsg(err instanceof ApiError ? err.detail : 'Order failed'),
  });

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Rewind className="h-5 w-5 text-cyan" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">{t('rep.title')}</h2>
            <p className="text-xs text-mute">{t('rep.subtitle')}</p>
          </div>
        </div>
      </div>

      <Panel>
        <div className="flex flex-wrap items-end gap-3 p-4">
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('mkt.pair')}</span>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs">
              {markets.map((m) => (
                <option key={m.symbol} value={m.symbol}>{m.symbol}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('term.timeframe')}</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs">
              {TIMEFRAMES.map((tf) => (
                <option key={tf.id} value={tf.id}>{tf.id}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={startMut.isPending}
            onClick={() => startMut.mutate({ symbol, timeframe, bars: 160, start_cursor: 40 })}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            {t('rep.start')}
          </button>

          {session && (
            <div className="ms-auto flex flex-wrap items-center gap-2">
              <span className="num font-mono text-xs text-mute">
                {t('rep.progress', { curr: session.cursor_index + 1, total: session.total_bars })}
              </span>
              <button type="button" onClick={() => stepMut.mutate({ id: session.id, steps: 1 })} className="inline-flex min-h-[34px] items-center gap-1 rounded border border-line bg-surface px-2.5 text-xs hover:border-cyan">
                <StepForward className="h-3.5 w-3.5" aria-hidden="true" />
                {t('rep.step1')}
              </button>
              <button type="button" onClick={() => stepMut.mutate({ id: session.id, steps: 5 })} className="inline-flex min-h-[34px] items-center gap-1 rounded border border-line bg-surface px-2.5 text-xs hover:border-cyan">
                <FastForward className="h-3.5 w-3.5" aria-hidden="true" />
                {t('rep.step5')}
              </button>
              <button type="button" onClick={() => stepMut.mutate({ id: session.id, steps: 20 })} className="inline-flex min-h-[34px] items-center gap-1 rounded border border-line bg-surface px-2.5 text-xs hover:border-cyan">
                {t('rep.step20')}
              </button>
            </div>
          )}
        </div>
        {errMsg && <p className="border-t border-line px-4 py-2 text-xs text-bear">{errMsg}</p>}
      </Panel>

      {session && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <MetricCard label="Cash USDT" value={`$${fmtPrice(session.state.cash_usdt)}`} tip="Replay virtual cash" />
            <MetricCard label="Position Qty" value={session.state.position_qty.toFixed(6)} tip="Replay position size" />
            <MetricCard label="Unrealized PnL" value={`$${session.state.unrealized_pnl_usdt.toFixed(2)}`} tip="Mark-to-market replay PnL" />
            <MetricCard label="Realized PnL" value={`$${session.state.realized_pnl_usdt.toFixed(2)}`} tip="Closed replay PnL" />
            <MetricCard label="Total Equity" value={`$${fmtPrice(session.state.total_equity_usdt)}`} tip="Cash + position value" />
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <Panel>
              <div className="h-[52vh] min-h-[320px] w-full">
                <TradingChart candles={session.visible_candles} theme={theme} />
              </div>
            </Panel>

            <Panel title="Replay Execution">
              <div className="space-y-3 p-4 text-xs">
                <p className="num text-mute">
                  Current Close: <span className="font-semibold text-ink">{session.current_bar ? fmtPrice(session.current_bar.close) : '—'}</span>
                </p>
                <label className="block space-y-1">
                  <span className="text-mute">Order Qty</span>
                  <input
                    type="number"
                    step="0.001"
                    min={0.0001}
                    value={orderQty}
                    onChange={(e) => setOrderQty(Number(e.target.value))}
                    className="min-h-[36px] w-full rounded border border-line bg-surface px-2.5 tabular-nums"
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => orderMut.mutate({ id: session.id, side: 'buy', qty: orderQty })}
                    className="min-h-[36px] rounded bg-bull/20 font-medium text-bull hover:bg-bull/30"
                  >
                    {t('rep.buy')}
                  </button>
                  <button
                    type="button"
                    onClick={() => orderMut.mutate({ id: session.id, side: 'sell', qty: orderQty })}
                    className="min-h-[36px] rounded bg-bear/20 font-medium text-bear hover:bg-bear/30"
                  >
                    {t('rep.sell')}
                  </button>
                </div>
                <div className="border-t border-line pt-2">
                  <p className="mb-1 font-semibold">Trades ({session.state.trades.length})</p>
                  <ul className="max-h-48 space-y-1 overflow-y-auto font-mono text-[11px]" dir="ltr">
                    {session.state.trades.map((tr, i) => (
                      <li key={i} className="flex justify-between">
                        <span className={tr.side === 'buy' ? 'text-bull' : 'text-bear'}>{tr.side.toUpperCase()}</span>
                        <span>{tr.qty} @ {fmtPrice(tr.price)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
