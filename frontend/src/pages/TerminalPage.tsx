import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Minus,
  MousePointer,
  PanelLeft,
  PanelRight,
  Plus,
  Ruler,
  Trash2,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { generateDemoCandles, seedFromString } from '@/features/chart/demoCandles';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import {
  TradingChart,
  type ChartDrawing,
  type DrawMode,
} from '@/features/chart/TradingChart';
import { DynamicParamFields } from '@/features/indicators/DynamicParamFields';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import type { TKey } from '@/i18n/en';
import { useT } from '@/i18n/useT';
import {
  computeIndicators,
  createIndicatorPreset,
  fetchIndicatorCatalog,
  fetchMarketOrderBook,
  fetchMarketTrades,
  listIndicatorPresets,
  updateIndicatorPreset,
  type CandleMode,
} from '@/services/api';
import { useUiStore } from '@/stores/uiStore';
import { DemoBadge } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
import { LiveBadge } from '@/ui/LiveBadge';
import { Panel } from '@/ui/Panel';
import { fmtCompact, fmtPct, fmtPrice } from '@/utils/format';

const BOTTOM_TABS: { id: string; labelKey: TKey }[] = [
  { id: 'positions', labelKey: 'term.tab.positions' },
  { id: 'orders', labelKey: 'term.tab.orders' },
  { id: 'history', labelKey: 'term.tab.history' },
  { id: 'log', labelKey: 'term.tab.log' },
];

export function TerminalPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const theme = useUiStore((s) => s.theme);
  const [params, setParams] = useSearchParams();

  const { rows: markets, isLive: isMarketsLive } = useLiveMarkets();
  const fallback = markets[0]!;
  const market = markets.find((m) => m.symbol === params.get('symbol')) ?? fallback;

  const [tfId, setTfId] = useState('15m');
  const [candleMode, setCandleMode] = useState<CandleMode>('standard');
  const [drawMode, setDrawMode] = useState<DrawMode>('none');
  const [drawings, setDrawings] = useState<ChartDrawing[]>([]);
  const [pendingFibPrice, setPendingFibPrice] = useState<number | null>(null);
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [showAddInd, setShowAddInd] = useState(false);
  const [newIndId, setNewIndId] = useState('macd');
  const [newIndParams, setNewIndParams] = useState<Record<string, number | string>>({});
  const [bottomTab, setBottomTab] = useState('positions');

  const tf = TIMEFRAMES.find((x) => x.id === tfId) ?? TIMEFRAMES[3]!;

  const { data: catalogData } = useQuery({
    queryKey: ['indicator-catalog'],
    queryFn: fetchIndicatorCatalog,
    retry: 1,
  });

  const { data: presetsData } = useQuery({
    queryKey: ['indicator-presets'],
    queryFn: listIndicatorPresets,
    retry: 1,
  });

  const presets = presetsData?.items ?? [];
  const activePresets = useMemo(() => presets.filter((p) => p.visible), [presets]);
  const activeSignature = useMemo(
    () => activePresets.map((p) => `${p.id}:${JSON.stringify(p.params)}`).join('|'),
    [activePresets],
  );

  const togglePresetMut = useMutation({
    mutationFn: ({ id, visible }: { id: string; visible: boolean }) =>
      updateIndicatorPreset(id, { visible }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['indicator-presets'] }),
  });

  const addPresetMut = useMutation({
    mutationFn: createIndicatorPreset,
    onSuccess: () => {
      setShowAddInd(false);
      queryClient.invalidateQueries({ queryKey: ['indicator-presets'] });
    },
  });

  const selectedAddSpec = useMemo(
    () => (catalogData?.items ?? []).find((c) => c.id === newIndId) ?? null,
    [catalogData, newIndId],
  );

  const {
    data: computeData,
    isError: isComputeError,
    isFetching: isCandlesFetching,
  } = useQuery({
    queryKey: ['mexc-compute', market.symbol, tf.id, candleMode, activeSignature],
    queryFn: () =>
      computeIndicators({
        symbol: market.symbol,
        timeframe: tf.id,
        limit: 250,
        candle_mode: candleMode,
        indicators: activePresets.map((p) => ({
          instance_id: p.id,
          indicator_id: p.indicator_id,
          params: p.params,
        })),
      }),
    refetchInterval: 15_000,
    retry: 1,
  });

  const { data: orderBook } = useQuery({
    queryKey: ['mexc-orderbook', market.symbol],
    queryFn: () => fetchMarketOrderBook(market.symbol, 8),
    refetchInterval: 10_000,
    retry: 1,
  });

  const { data: recentTrades } = useQuery({
    queryKey: ['mexc-trades', market.symbol],
    queryFn: () => fetchMarketTrades(market.symbol, 12),
    refetchInterval: 10_000,
    retry: 1,
  });

  const demoCandles = useMemo(() => {
    const endTime = Math.floor(Date.now() / 1000 / tf.seconds) * tf.seconds;
    return generateDemoCandles({
      count: 220,
      stepSeconds: tf.seconds,
      seed: seedFromString(`${market.symbol}|${tf.id}`),
      startPrice: market.last,
      endTime,
    });
  }, [market.symbol, market.last, tf.id, tf.seconds]);

  const hasLiveCandles = Boolean(computeData?.candles?.length) && !isComputeError;
  const candles = hasLiveCandles ? computeData!.candles : demoCandles;
  const overlays = useMemo(
    () => (hasLiveCandles ? computeData!.outputs.filter((o) => o.pane === 'overlay') : []),
    [hasLiveCandles, computeData],
  );
  const oscillators = useMemo(
    () => (hasLiveCandles ? computeData!.outputs.filter((o) => o.pane === 'oscillator') : []),
    [hasLiveCandles, computeData],
  );

  const gridCls =
    showLeft && showRight
      ? 'lg:grid-cols-[14rem_minmax(0,1fr)_17rem]'
      : showLeft
        ? 'lg:grid-cols-[14rem_minmax(0,1fr)]'
        : showRight
          ? 'lg:grid-cols-[minmax(0,1fr)_17rem]'
          : 'lg:grid-cols-1';

  const toggleBtn = (active: boolean) =>
    `flex h-11 w-11 items-center justify-center rounded border border-line sm:h-8 sm:w-8 ${
      active ? 'bg-elevated text-cyan' : 'text-mute hover:text-ink'
    }`;

  return (
    <div className="mx-auto flex max-w-[1920px] flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="num text-lg font-semibold">{market.symbol}</h2>
          <span className="num text-lg">{fmtPrice(market.last)}</span>
          <span className={`num text-sm font-medium ${market.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>
            {fmtPct(market.change24h)}
          </span>
          {hasLiveCandles || isMarketsLive ? <LiveBadge /> : <DemoBadge />}
        </div>
        <div className="flex items-center gap-2" role="group" aria-label={t('term.togglePanels')}>
          <button
            type="button"
            aria-pressed={showLeft}
            aria-label={t('term.watchlist')}
            title={t('term.watchlist')}
            onClick={() => setShowLeft((v) => !v)}
            className={toggleBtn(showLeft)}
          >
            <PanelLeft className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-pressed={showRight}
            aria-label={t('term.orderBook')}
            title={t('term.orderBook')}
            onClick={() => setShowRight((v) => !v)}
            className={toggleBtn(showRight)}
          >
            <PanelRight className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className={`grid gap-3 ${gridCls}`}>
        {/* Left: watchlist */}
        {showLeft && (
          <Panel title={t('term.watchlist')} className="order-2 max-h-[420px] overflow-hidden lg:order-1 lg:max-h-none">
            <ul className="max-h-[360px] overflow-y-auto lg:max-h-[64vh]">
              {markets.map((m) => {
                const active = m.symbol === market.symbol;
                return (
                  <li key={m.symbol}>
                    <button
                      type="button"
                      onClick={() => setParams({ symbol: m.symbol })}
                      aria-current={active}
                      className={`flex min-h-[44px] w-full items-center justify-between gap-2 border-s-2 px-3 text-sm sm:min-h-[38px] ${
                        active ? 'border-cyan bg-elevated' : 'border-transparent hover:bg-surface'
                      }`}
                    >
                      <span className="num font-medium">{m.symbol}</span>
                      <span className={`num text-xs ${m.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>
                        {fmtPct(m.change24h)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Panel>
        )}

        {/* Center: chart + toolbars */}
        <Panel className="order-1 lg:order-2">
          {/* Timeframes + Candle Mode */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line p-2">
            <div className="flex gap-1 overflow-x-auto" role="group" aria-label={t('term.timeframe')}>
              {TIMEFRAMES.map((x) => (
                <button
                  key={x.id}
                  type="button"
                  aria-pressed={x.id === tf.id}
                  onClick={() => setTfId(x.id)}
                  className={`min-h-[36px] min-w-[36px] shrink-0 rounded px-2 text-xs font-medium sm:min-h-[30px] ${
                    x.id === tf.id ? 'bg-elevated text-cyan' : 'text-mute hover:bg-surface hover:text-ink'
                  }`}
                >
                  {x.id}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5" role="group" aria-label={t('term.candleMode')}>
              <button
                type="button"
                onClick={() => setCandleMode('standard')}
                className={`min-h-[30px] rounded border px-2 text-[11px] font-medium ${
                  candleMode === 'standard'
                    ? 'border-cyan bg-elevated text-cyan'
                    : 'border-line bg-surface text-mute hover:text-ink'
                }`}
              >
                {t('term.modeStandard')}
              </button>
              <button
                type="button"
                onClick={() => setCandleMode('heikin_ashi')}
                className={`min-h-[30px] rounded border px-2 text-[11px] font-medium ${
                  candleMode === 'heikin_ashi'
                    ? 'border-cyan bg-elevated text-cyan'
                    : 'border-line bg-surface text-mute hover:text-ink'
                }`}
              >
                {t('term.modeHeikinAshi')}
              </button>
            </div>
          </div>

          {/* Drawing tools & Indicator Presets bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface/40 px-2 py-1.5 text-xs">
            <div className="flex flex-wrap items-center gap-1" role="group" aria-label={t('term.drawTools')}>
              <button
                type="button"
                onClick={() => {
                  setDrawMode('none');
                  setPendingFibPrice(null);
                }}
                title={t('term.drawPointer')}
                className={`inline-flex min-h-[28px] items-center gap-1 rounded border px-2 text-[11px] ${
                  drawMode === 'none' ? 'border-cyan bg-elevated text-cyan' : 'border-line bg-surface text-mute'
                }`}
              >
                <MousePointer className="h-3 w-3" aria-hidden="true" />
                {t('term.drawPointer')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setDrawMode('hline');
                  setPendingFibPrice(null);
                }}
                title={t('term.drawHline')}
                className={`inline-flex min-h-[28px] items-center gap-1 rounded border px-2 text-[11px] ${
                  drawMode === 'hline' ? 'border-cyan bg-elevated text-cyan' : 'border-line bg-surface text-mute'
                }`}
              >
                <Minus className="h-3 w-3" aria-hidden="true" />
                {t('term.drawHline')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setDrawMode('fib');
                  setPendingFibPrice(null);
                }}
                title={t('term.drawFib')}
                className={`inline-flex min-h-[28px] items-center gap-1 rounded border px-2 text-[11px] ${
                  drawMode === 'fib' ? 'border-cyan bg-elevated text-cyan' : 'border-line bg-surface text-mute'
                }`}
              >
                <Ruler className="h-3 w-3" aria-hidden="true" />
                {t('term.drawFib')}
              </button>
              {drawings.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setDrawings([]);
                    setPendingFibPrice(null);
                  }}
                  className="inline-flex min-h-[28px] items-center gap-1 rounded border border-line bg-surface px-2 text-[11px] text-bear hover:border-bear"
                >
                  <Trash2 className="h-3 w-3" aria-hidden="true" />
                  {t('term.drawClear')} ({drawings.length})
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-1">
              <span className="me-1 text-[11px] text-mute">{t('term.indicators')}:</span>
              {presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => togglePresetMut.mutate({ id: p.id, visible: !p.visible })}
                  aria-pressed={p.visible}
                  className={`inline-flex min-h-[28px] items-center gap-1 rounded border px-2 text-[11px] ${
                    p.visible
                      ? 'border-cyan/50 bg-cyan/10 text-cyan'
                      : 'border-line bg-surface text-mute hover:text-ink'
                  }`}
                >
                  <Activity className="h-3 w-3" aria-hidden="true" />
                  {p.name}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  setShowAddInd((v) => !v);
                  if (selectedAddSpec) {
                    const defs: Record<string, number | string> = {};
                    for (const pm of selectedAddSpec.parameters) defs[pm.name] = pm.default;
                    setNewIndParams(defs);
                  }
                }}
                className="inline-flex min-h-[28px] items-center gap-1 rounded border border-line bg-surface px-2 text-[11px] hover:border-cyan"
              >
                <Plus className="h-3 w-3 text-cyan" aria-hidden="true" />
                {t('term.addIndicator')}
              </button>
              <Link
                to="/indicator-library"
                className="inline-flex min-h-[28px] items-center rounded border border-line bg-surface px-2 text-[11px] text-mute hover:text-cyan"
              >
                {t('term.manageLibrary')}
              </Link>
            </div>
          </div>

          {/* Pending fib prompt */}
          {drawMode === 'fib' && pendingFibPrice !== null && (
            <p className="border-b border-line bg-amber/10 px-3 py-1 text-[11px] text-amber">
              {t('term.fibPrompt')}
            </p>
          )}

          {/* Quick Add Indicator Panel */}
          {showAddInd && catalogData?.items && (
            <div className="space-y-3 border-b border-line bg-surface/60 p-3">
              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={newIndId}
                  onChange={(e) => {
                    const nextId = e.target.value;
                    setNewIndId(nextId);
                    const spec = catalogData.items.find((c) => c.id === nextId);
                    if (spec) {
                      const defs: Record<string, number | string> = {};
                      for (const pm of spec.parameters) defs[pm.name] = pm.default;
                      setNewIndParams(defs);
                    }
                  }}
                  className="min-h-[36px] rounded border border-line bg-surface px-2.5 text-xs"
                >
                  {catalogData.items.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
                {isCandlesFetching && <span className="text-xs text-mute">{t('common.loading')}</span>}
              </div>
              {selectedAddSpec && (
                <>
                  <DynamicParamFields
                    parameters={selectedAddSpec.parameters}
                    values={newIndParams}
                    onChange={(k, v) => setNewIndParams((prev) => ({ ...prev, [k]: v }))}
                  />
                  <button
                    type="button"
                    disabled={addPresetMut.isPending}
                    onClick={() =>
                      addPresetMut.mutate({
                        indicator_id: selectedAddSpec.id,
                        name: `${selectedAddSpec.id.toUpperCase()} (${Object.values(newIndParams)[0] ?? ''})`,
                        symbol: market.symbol,
                        timeframe: tf.id,
                        params: newIndParams,
                        visible: true,
                      })
                    }
                    className="min-h-[34px] rounded bg-cyan px-3 text-xs font-medium text-bg hover:opacity-90"
                  >
                    {t('common.save')}
                  </button>
                </>
              )}
            </div>
          )}

          {/* Chart canvas (+ synced oscillator pane) */}
          <div className={oscillators.length > 0 ? 'h-[62vh] min-h-[440px] w-full' : 'h-[52vh] min-h-[300px] w-full'}>
            <TradingChart
              candles={candles}
              theme={theme}
              overlays={overlays}
              oscillators={oscillators}
              drawMode={drawMode}
              drawings={drawings}
              pendingFibPrice={pendingFibPrice}
              onPendingFibChange={setPendingFibPrice}
              onAddDrawing={(d) => setDrawings((prev) => [...prev, d])}
            />
          </div>

          {hasLiveCandles ? (
            <p className="border-t border-line px-3 py-1.5 font-mono text-[11px] text-mute" dir="ltr">
              {t('chart.liveQuality', {
                source: `${computeData!.source} (${computeData!.candle_mode})`,
                bars: computeData!.quality.total_bars,
                gaps: computeData!.quality.gap_count,
                hash: computeData!.quality.data_snapshot_hash.slice(0, 12),
              })}
            </p>
          ) : (
            <p className="border-t border-line px-3 py-1.5 text-[11px] text-amber">{t('chart.demoNote')}</p>
          )}
        </Panel>

        {/* Right: live order book + recent trades + stats */}
        {showRight && (
          <div className="order-3 flex flex-col gap-3">
            <Panel title={t('term.orderBook')} actions={orderBook ? <LiveBadge /> : undefined}>
              {!orderBook ? (
                <EmptyState title={t('common.notConnected')} body={t('term.orderBookNeeds')} />
              ) : (
                <div className="space-y-2 p-2.5 text-xs" dir="ltr">
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px] text-mute">
                      <span>{t('term.asks')}</span>
                      <span>Qty</span>
                    </div>
                    {orderBook.asks
                      .slice(0, 6)
                      .reverse()
                      .map(([price, qty], i) => (
                        <div key={`ask-${i}`} className="num flex justify-between font-mono text-bear">
                          <span>{fmtPrice(price)}</span>
                          <span className="text-ink">{qty.toFixed(4)}</span>
                        </div>
                      ))}
                  </div>
                  <div className="flex items-center justify-between border-y border-line py-1 text-[11px] text-mute">
                    <span>{t('term.spread')}</span>
                    <span className="num font-mono text-ink">
                      {fmtPrice(orderBook.spread)} ({orderBook.spread_pct.toFixed(3)}%)
                    </span>
                  </div>
                  <div className="space-y-0.5">
                    <div className="flex justify-between text-[11px] text-mute">
                      <span>{t('term.bids')}</span>
                      <span>Qty</span>
                    </div>
                    {orderBook.bids.slice(0, 6).map(([price, qty], i) => (
                      <div key={`bid-${i}`} className="num flex justify-between font-mono text-bull">
                        <span>{fmtPrice(price)}</span>
                        <span className="text-ink">{qty.toFixed(4)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Panel>

            <Panel title={t('term.recentTrades')}>
              {!recentTrades?.items?.length ? (
                <p className="p-3 text-xs text-mute">{t('term.orderBookNeeds')}</p>
              ) : (
                <ul className="max-h-44 divide-y divide-line/60 overflow-y-auto px-2.5 py-1 text-[11px]" dir="ltr">
                  {recentTrades.items.slice(0, 10).map((tr, idx) => (
                    <li key={`${tr.time}-${idx}`} className="num flex justify-between py-1 font-mono">
                      <span className={tr.side === 'buy' ? 'text-bull' : 'text-bear'}>{fmtPrice(tr.price)}</span>
                      <span className="text-ink">{tr.qty.toFixed(4)}</span>
                      <span className="text-mute">{new Date(tr.time).toLocaleTimeString()}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title={t('term.stats')} actions={isMarketsLive ? <LiveBadge /> : <DemoBadge />}>
              <dl className="grid grid-cols-2 gap-2 p-3 text-xs">
                <dt className="text-mute">{t('mkt.high')}</dt>
                <dd className="num text-end">{fmtPrice(market.high)}</dd>
                <dt className="text-mute">{t('mkt.low')}</dt>
                <dd className="num text-end">{fmtPrice(market.low)}</dd>
                <dt className="text-mute">{t('mkt.volume')}</dt>
                <dd className="num text-end">{fmtCompact(market.volume24h)}</dd>
              </dl>
            </Panel>
          </div>
        )}
      </div>

      {/* Bottom panel */}
      <Panel>
        <div role="tablist" aria-label={t('nav.terminal')} className="flex overflow-x-auto border-b border-line">
          {BOTTOM_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={bottomTab === tab.id}
              onClick={() => setBottomTab(tab.id)}
              className={`min-h-[44px] shrink-0 border-b-2 px-4 text-xs font-medium sm:min-h-[36px] ${
                bottomTab === tab.id ? 'border-cyan text-ink' : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              {t(tab.labelKey)}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          <EmptyState title={t(BOTTOM_TABS.find((x) => x.id === bottomTab)!.labelKey)} body={t('term.bottomEmpty')} />
        </div>
      </Panel>
    </div>
  );
}
