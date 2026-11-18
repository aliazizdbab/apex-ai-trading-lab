import { useQuery } from '@tanstack/react-query';
import { Activity, BookOpen, Bot, Layers, Plug } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { DEMO_METRICS } from '@/features/market/demoData';
import { MarketTable } from '@/features/market/MarketTable';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { fetchLiveOverview, fetchPaperOverview, listBacktests, listStrategies } from '@/services/api';
import { useUiStore } from '@/stores/uiStore';
import { DemoBadge } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
import { LiveBadge } from '@/ui/LiveBadge';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';
import { fmtPrice } from '@/utils/format';

type Account = 'real' | 'paper';

export function DashboardPage() {
  const t = useT();
  const toggleCopilot = useUiStore((s) => s.toggleCopilot);
  const [account, setAccount] = useState<Account>('paper');
  const { rows, isLive } = useLiveMarkets();

  const { data: paper } = useQuery({ queryKey: ['paper-overview'], queryFn: fetchPaperOverview, retry: false });
  const { data: live } = useQuery({ queryKey: ['live-overview'], queryFn: fetchLiveOverview, retry: false });
  const { data: stratsData } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies, retry: false });
  const { data: btData } = useQuery({ queryKey: ['backtests'], queryFn: listBacktests, retry: false });

  const strategies = stratsData?.items ?? [];
  const backtests = btData?.items ?? [];
  const paperOrders = paper?.orders ?? [];
  const m = DEMO_METRICS;
  const period = t('dash.vs24h');

  const portfolioVal = paper?.account.total_equity_usdt ?? m.portfolio.value;
  const availableUsdt = paper?.account.available_usdt ?? m.availableUsdt.value;
  const unrealized = paper?.account.unrealized_pnl_usdt ?? 0;
  const realized = paper?.account.realized_pnl_usdt ?? 0;

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold sm:text-lg">{t('dash.title')}</h2>
          {account === 'paper' && <DemoBadge />}
        </div>
        <Segmented<Account>
          ariaLabel={t('dash.title')}
          value={account}
          onChange={setAccount}
          options={[
            { value: 'real', label: t('dash.accountReal') },
            { value: 'paper', label: t('dash.accountPaper') },
          ]}
        />
      </div>

      {/* Onboarding Guide & AI Copilot Quick Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-cyan/30 bg-cyan/10 p-3 text-xs">
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-cyan">{t('guide.bannerTitle')}</div>
          <p className="mt-0.5 text-mute">{t('guide.bannerBody')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/guide"
            className="inline-flex min-h-[34px] items-center gap-1.5 rounded bg-cyan px-3 text-xs font-semibold text-base hover:bg-cyan/90"
          >
            <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
            {t('nav.guide')}
          </Link>
          <button
            type="button"
            onClick={toggleCopilot}
            className="inline-flex min-h-[34px] items-center gap-1.5 rounded border border-cyan/50 bg-panel px-3 text-xs font-medium text-ink hover:border-cyan"
          >
            <Bot className="h-3.5 w-3.5 text-cyan" aria-hidden="true" />
            {t('copilot.button')}
          </button>
        </div>
      </div>

      {account === 'paper' ? (
        <div className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-4 xl:grid-cols-7">
          <MetricCard label={t('dash.portfolio')} value={`$${fmtPrice(portfolioVal)}`} deltaPct={m.portfolio.deltaPct} period={period} spark={m.portfolio.spark} tip={t('dash.tip.portfolio')} />
          <MetricCard label={t('dash.availableUsdt')} value={`$${fmtPrice(availableUsdt)}`} tip={t('dash.tip.usdt')} spark={m.availableUsdt.spark} />
          <MetricCard label={t('dash.unrealized')} value={`$${unrealized.toFixed(2)}`} period={period} tip={t('dash.tip.unrealized')} />
          <MetricCard label={t('dash.realized')} value={`$${realized.toFixed(2)}`} period={period} tip={t('dash.tip.realized')} />
          <MetricCard label={t('dash.todayReturn')} value={`${m.todayReturn.value.toFixed(2)}%`} deltaPct={m.todayReturn.deltaPct} period={period} spark={m.todayReturn.spark} tip={t('dash.tip.today')} />
          <MetricCard label={t('dash.activeStrategies')} value={String(strategies.length)} tip={t('dash.tip.strategies')} />
          <MetricCard label={t('dash.openPositions')} value={String(paper?.positions.length ?? 0)} tip={t('dash.tip.positions')} />
        </div>
      ) : (
        <Panel>
          {live?.exchange_credentials_configured ? (
            <div className="grid grid-cols-2 gap-3 p-3 sm:grid-cols-3">
              <MetricCard label={t('dash.realized')} value={`$${(live.realized_pnl_usdt ?? 0).toFixed(2)}`} tip={t('dash.tip.realized')} />
              <MetricCard label={t('dash.openPositions')} value={String(live.positions.length)} tip={t('dash.tip.positions')} />
              <MetricCard label={t('dash.activeStrategies')} value={String(live.authorizations.filter((a) => a.active).length)} tip={t('dash.tip.strategies')} />
            </div>
          ) : (
            <EmptyState icon={Plug} title={t('dash.realEmptyTitle')} body={t('dash.realEmptyBody')}>
              <Link to="/exchanges" className="mt-1 rounded border border-cyan/50 bg-cyan/10 px-3 py-1.5 text-xs font-medium text-cyan hover:bg-cyan/20">
                {t('nav.exchanges')}
              </Link>
            </EmptyState>
          )}
        </Panel>
      )}

      <Panel title={t('dash.markets')} actions={isLive ? <LiveBadge /> : <DemoBadge />}>
        <MarketTable rows={rows} />
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title={t('dash.strategiesTitle')}
          actions={
            <Link to="/strategy-composer" className="text-xs text-cyan hover:underline">
              {t('nav.strategyComposer')}
            </Link>
          }
        >
          {strategies.length === 0 ? (
            <EmptyState icon={Layers} title={t('nav.strategyLibrary')} body={t('strat.composerSub')} />
          ) : (
            <ul className="divide-y divide-line">
              {strategies.slice(0, 5).map((s) => (
                <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold text-ink">{s.name}</div>
                    <div className="text-mute">
                      {s.current_version?.definition.symbol ?? 'BTC/USDT'} · {s.current_version?.definition.timeframe ?? '15m'} · v
                      {s.current_version?.version_no ?? 1}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-surface px-2 py-0.5 text-[11px] font-medium text-cyan">{s.status}</span>
                    <Link
                      to="/backtesting"
                      className="rounded border border-line bg-surface px-2 py-1 text-[11px] text-ink hover:border-cyan"
                    >
                      {t('nav.backtesting')}
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title={t('dash.activityTitle')}
          actions={
            <Link to="/backtesting" className="text-xs text-cyan hover:underline">
              {t('nav.backtesting')}
            </Link>
          }
        >
          {backtests.length === 0 && paperOrders.length === 0 ? (
            <div className="flex flex-col items-center gap-2 p-6 text-center text-xs text-mute">
              <Activity className="h-7 w-7 text-cyan" aria-hidden="true" />
              <p>{t('guide.noActivityHint')}</p>
              <div className="flex flex-wrap justify-center gap-2 pt-1">
                <Link to="/backtesting" className="rounded bg-cyan px-3 py-1.5 font-semibold text-base">
                  {t('nav.backtesting')}
                </Link>
                <Link to="/paper-trading" className="rounded border border-line bg-surface px-3 py-1.5 text-ink">
                  {t('nav.paperTrading')}
                </Link>
              </div>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {backtests.slice(0, 4).map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-2 px-3 py-2.5 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold">{b.strategy_name}</div>
                    <div className="text-mute">
                      {b.symbol} · {b.timeframe} · {b.total_trades} trades
                    </div>
                  </div>
                  <span className={`num font-semibold ${b.total_return_pct >= 0 ? 'text-bull' : 'text-bear'}`}>
                    {b.total_return_pct.toFixed(2)}%
                  </span>
                </li>
              ))}
              {paperOrders.slice(0, 3).map((o) => (
                <li key={o.id} className="flex items-center justify-between gap-2 px-3 py-2.5 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold">
                      Paper {o.side.toUpperCase()} {o.symbol}
                    </div>
                    <div className="text-mute">Qty {o.qty}</div>
                  </div>
                  <span className="rounded bg-surface px-2 py-0.5 text-[11px] text-cyan">{o.status}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
