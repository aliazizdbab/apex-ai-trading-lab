import { PanelLeft, PanelRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { generateDemoCandles, seedFromString } from '@/features/chart/demoCandles';
import { TIMEFRAMES } from '@/features/chart/timeframes';
import { TradingChart } from '@/features/chart/TradingChart';
import { DEMO_MARKETS } from '@/features/market/demoData';
import type { TKey } from '@/i18n/en';
import { useT } from '@/i18n/useT';
import { useUiStore } from '@/stores/uiStore';
import { DemoBadge } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
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
  const theme = useUiStore((s) => s.theme);
  const [params, setParams] = useSearchParams();

  const fallback = DEMO_MARKETS[0]!;
  const market = DEMO_MARKETS.find((m) => m.symbol === params.get('symbol')) ?? fallback;

  const [tfId, setTfId] = useState('15m');
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [bottomTab, setBottomTab] = useState('positions');

  const tf = TIMEFRAMES.find((x) => x.id === tfId) ?? TIMEFRAMES[3]!;

  const candles = useMemo(() => {
    const endTime = Math.floor(Date.now() / 1000 / tf.seconds) * tf.seconds;
    return generateDemoCandles({
      count: 220,
      stepSeconds: tf.seconds,
      seed: seedFromString(`${market.symbol}|${tf.id}`),
      startPrice: market.last,
      endTime,
    });
  }, [market.symbol, market.last, tf.id, tf.seconds]);

  const gridCls =
    showLeft && showRight
      ? 'lg:grid-cols-[14rem_minmax(0,1fr)_16rem]'
      : showLeft
        ? 'lg:grid-cols-[14rem_minmax(0,1fr)]'
        : showRight
          ? 'lg:grid-cols-[minmax(0,1fr)_16rem]'
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
          <span className={`num text-sm font-medium ${market.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>{fmtPct(market.change24h)}</span>
          <DemoBadge />
        </div>
        <div className="flex items-center gap-2" role="group" aria-label={t('term.togglePanels')}>
          <button type="button" aria-pressed={showLeft} aria-label={t('term.watchlist')} title={t('term.watchlist')} onClick={() => setShowLeft((v) => !v)} className={toggleBtn(showLeft)}>
            <PanelLeft className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
          </button>
          <button type="button" aria-pressed={showRight} aria-label={t('term.orderBook')} title={t('term.orderBook')} onClick={() => setShowRight((v) => !v)} className={toggleBtn(showRight)}>
            <PanelRight className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className={`grid gap-3 ${gridCls}`}>
        {/* Left: watchlist */}
        {showLeft && (
          <Panel title={t('term.watchlist')} className="order-2 max-h-[420px] overflow-hidden lg:order-1 lg:max-h-none">
            <ul className="max-h-[360px] overflow-y-auto lg:max-h-[60vh]">
              {DEMO_MARKETS.map((m) => {
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
                      <span className={`num text-xs ${m.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>{fmtPct(m.change24h)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Panel>
        )}

        {/* Center: chart */}
        <Panel className="order-1 lg:order-2">
          <div className="flex gap-1 overflow-x-auto border-b border-line p-2" role="group" aria-label={t('term.timeframe')}>
            {TIMEFRAMES.map((x) => (
              <button
                key={x.id}
                type="button"
                aria-pressed={x.id === tf.id}
                onClick={() => setTfId(x.id)}
                className={`min-h-[44px] min-w-[44px] shrink-0 rounded px-2 text-xs font-medium sm:min-h-[32px] sm:min-w-[36px] ${
                  x.id === tf.id ? 'bg-elevated text-cyan' : 'text-mute hover:bg-surface hover:text-ink'
                }`}
              >
                {x.id}
              </button>
            ))}
          </div>
          <div className="h-[52vh] min-h-[300px] w-full">
            <TradingChart candles={candles} theme={theme} />
          </div>
          <p className="border-t border-line px-3 py-1.5 text-[11px] text-amber">{t('chart.demoNote')}</p>
        </Panel>

        {/* Right: order book + stats */}
        {showRight && (
          <div className="order-3 flex flex-col gap-3">
            <Panel title={t('term.orderBook')}>
              <EmptyState title={t('common.notBuilt')} body={t('term.orderBookNeeds')} />
            </Panel>
            <Panel title={t('term.stats')} actions={<DemoBadge />}>
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
