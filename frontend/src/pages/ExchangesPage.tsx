import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Download, Plug, RefreshCw } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import {
  ApiError,
  backfillMarketCandles,
  fetchMarketCoverage,
  fetchMexcStatus,
} from '@/services/api';
import { LiveBadge } from '@/ui/LiveBadge';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';

export function ExchangesPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const { rows } = useLiveMarkets();

  const { data: statusData, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['mexc-exchange-status'],
    queryFn: fetchMexcStatus,
    retry: 1,
  });

  const { data: coverageData, isLoading: covLoading } = useQuery({
    queryKey: ['mexc-coverage'],
    queryFn: fetchMarketCoverage,
    retry: 1,
  });

  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [bars, setBars] = useState(300);
  const [backfillMsg, setBackfillMsg] = useState<string | null>(null);
  const [backfillErr, setBackfillErr] = useState<string | null>(null);

  const backfillMut = useMutation({
    mutationFn: backfillMarketCandles,
    onSuccess: (res) => {
      setBackfillErr(null);
      setBackfillMsg(
        `${res.symbol} (${res.timeframe}) · ${res.source} · ${res.quality.total_bars} bars · gaps=${res.quality.gap_count} · hash=${res.quality.data_snapshot_hash.slice(0, 12)}`,
      );
      queryClient.invalidateQueries({ queryKey: ['mexc-coverage'] });
    },
    onError: (err) => {
      setBackfillMsg(null);
      setBackfillErr(err instanceof ApiError ? err.detail : 'Backfill failed');
    },
  });

  const onBackfillSubmit = (e: FormEvent) => {
    e.preventDefault();
    backfillMut.mutate({ symbol, timeframe, bars });
  };

  const serverTimeStr = statusData?.server_time_ms
    ? new Date(statusData.server_time_ms).toISOString().replace('T', ' ').slice(0, 19)
    : '—';

  const inputCls =
    'min-h-[38px] w-full rounded border border-line bg-surface px-3 text-sm text-ink focus:border-cyan focus:outline-none';

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Plug className="h-5 w-5 text-cyan" aria-hidden="true" />
          <h2 className="text-lg font-semibold">{t('exchanges.title')}</h2>
          {statusData?.status === 'connected' && <LiveBadge />}
        </div>
        <button
          type="button"
          onClick={() => void refetchStatus()}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium hover:border-cyan"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${statusLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
          {t('common.refresh')}
        </button>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <MetricCard
          label={t('exchanges.connStatus')}
          value={statusData?.status === 'connected' ? t('status.connected') : t('status.disconnected')}
          tip={t('exchanges.connStatus')}
        />
        <MetricCard
          label={t('exchanges.latency')}
          value={statusData?.latency_ms != null ? `${statusData.latency_ms} ms` : '—'}
          tip={t('exchanges.latency')}
        />
        <MetricCard label={t('exchanges.serverTime')} value={serverTimeStr} tip={t('exchanges.serverTime')} />
        <MetricCard
          label={t('exchanges.storedKeys')}
          value={String(statusData?.stored_credentials_count ?? 0)}
          tip={t('exchanges.storedKeys')}
        />
        <MetricCard
          label={t('exchanges.rateLimiter')}
          value={
            statusData
              ? `${statusData.rate_limiter.available_tokens}/${statusData.rate_limiter.capacity}`
              : '—'
          }
          tip={t('exchanges.rateLimiter')}
        />
      </div>

      {/* Platform SL/TP explicit notice */}
      {statusData?.platform_sl_tp_required && (
        <Panel className="border-amber/40 bg-amber/5 p-3">
          <div className="flex items-start gap-2.5 text-xs">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber" aria-hidden="true" />
            <div className="space-y-1">
              <p className="font-semibold text-amber">{t('exchanges.slTpWarningTitle')}</p>
              <p className="text-mute">{statusData.platform_sl_tp_note}</p>
              <p className="text-mute">
                <span className="font-medium text-ink">{t('exchanges.orderTypes')}: </span>
                <span dir="ltr" className="font-mono">
                  {statusData.supported_order_types.join(', ')}
                </span>
              </p>
            </div>
          </div>
        </Panel>
      )}

      {/* Timeframes matrix + Symbol order rules */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t('exchanges.timeframesTitle')}>
          <div className="grid grid-cols-3 gap-2 p-3 sm:grid-cols-5">
            {(statusData?.timeframes ?? []).map((tf) => (
              <div key={tf.id} className="rounded border border-line bg-surface p-2 text-xs">
                <div className="num font-semibold">{tf.id}</div>
                <div className={`text-[11px] ${tf.mode === 'native' ? 'text-bull' : 'text-cyan'}`}>
                  {tf.mode === 'native'
                    ? t('exchanges.tfNative')
                    : t('exchanges.tfAggregated', { base: tf.aggregated_from ?? '' })}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title={t('exchanges.rulesTitle')}>
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start font-medium">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-end font-medium">{t('exchanges.pricePrec')}</th>
                  <th className="px-3 py-2 text-end font-medium">{t('exchanges.qtyPrec')}</th>
                  <th className="px-3 py-2 text-end font-medium">{t('exchanges.minQty')}</th>
                  <th className="px-3 py-2 text-end font-medium">{t('exchanges.minNotional')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {(statusData?.symbol_rules_sample ?? []).map((rule) => (
                  <tr key={rule.symbol}>
                    <td className="num px-3 py-2 font-semibold">{rule.symbol}</td>
                    <td className="num px-3 py-2 text-end">{rule.price_precision}</td>
                    <td className="num px-3 py-2 text-end">{rule.qty_precision}</td>
                    <td className="num px-3 py-2 text-end font-mono">{rule.min_qty}</td>
                    <td className="num px-3 py-2 text-end font-mono">{rule.min_notional}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      {/* Historical Backfill + Coverage */}
      <Panel title={t('exchanges.backfillTitle')}>
        <form onSubmit={onBackfillSubmit} className="grid gap-3 p-4 sm:grid-cols-4 sm:items-end">
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('mkt.pair')}</span>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputCls}>
              {rows.map((r) => (
                <option key={r.symbol} value={r.symbol}>
                  {r.symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('term.timeframe')}</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={inputCls}>
              {TIMEFRAMES.map((tf) => (
                <option key={tf.id} value={tf.id}>
                  {tf.id}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-mute">{t('exchanges.barsCount')}</span>
            <input
              type="number"
              min={50}
              max={1500}
              value={bars}
              onChange={(e) => setBars(Number(e.target.value))}
              className={`${inputCls} tabular-nums`}
            />
          </label>
          <button
            type="submit"
            disabled={backfillMut.isPending}
            className="inline-flex min-h-[38px] items-center justify-center gap-1.5 rounded bg-cyan px-4 text-xs font-medium text-bg hover:opacity-90 disabled:opacity-50"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {t('exchanges.runBackfill')}
          </button>
        </form>
        {backfillMsg && (
          <p className="border-t border-line px-4 py-2 font-mono text-xs text-bull" dir="ltr">
            {backfillMsg}
          </p>
        )}
        {backfillErr && <p className="border-t border-line px-4 py-2 text-xs text-bear">{backfillErr}</p>}
      </Panel>

      <Panel title={t('exchanges.coverageTitle')}>
        {covLoading ? (
          <p className="p-4 text-xs text-mute">{t('common.loading')}</p>
        ) : (coverageData?.coverage ?? []).length === 0 ? (
          <p className="p-4 text-xs text-mute">{t('exchanges.noCoverage')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start font-medium">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-start font-medium">{t('term.timeframe')}</th>
                  <th className="px-3 py-2 text-start font-medium">{t('exchanges.range')}</th>
                  <th className="px-3 py-2 text-end font-medium">{t('exchanges.gaps')}</th>
                  <th className="px-3 py-2 text-end font-medium">{t('exchanges.validatedAt')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {coverageData!.coverage.map((c) => (
                  <tr key={c.id}>
                    <td className="num px-3 py-2 font-semibold">{c.symbol}</td>
                    <td className="num px-3 py-2 font-mono">{c.timeframe}</td>
                    <td className="num px-3 py-2 font-mono text-mute" dir="ltr">
                      {c.from_ts.slice(0, 16).replace('T', ' ')} → {c.to_ts.slice(0, 16).replace('T', ' ')}
                    </td>
                    <td className={`num px-3 py-2 text-end font-medium ${c.gap_count === 0 ? 'text-bull' : 'text-amber'}`}>
                      {c.gap_count}
                    </td>
                    <td className="num px-3 py-2 text-end text-mute">
                      {new Date(c.validated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
