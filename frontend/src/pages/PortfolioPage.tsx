import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Wallet } from 'lucide-react';
import { useState } from 'react';
import { useT } from '@/i18n/useT';
import { fetchLiveOverview, fetchPaperOverview } from '@/services/api';
import { MetricCard } from '@/ui/MetricCard';
import { Panel } from '@/ui/Panel';
import { Segmented } from '@/ui/Segmented';
import { fmtPrice } from '@/utils/format';

export function PortfolioPage() {
  const t = useT();
  const [mode, setMode] = useState<'paper' | 'real'>('paper');
  const { data: paper } = useQuery({ queryKey: ['paper-overview'], queryFn: fetchPaperOverview });
  const { data: live } = useQuery({ queryKey: ['live-overview'], queryFn: fetchLiveOverview });

  const paperPositions = paper?.positions ?? [];
  const livePositions = live?.positions ?? [];
  const activePositions = mode === 'paper' ? paperPositions : livePositions;

  const liveExposureUsdt = livePositions.reduce((acc, p) => acc + Math.max(0, p.market_value_usdt), 0);
  const paperTotalEquity = paper?.account.total_equity_usdt ?? 10000;
  const activeTotalValue =
    mode === 'paper'
      ? Math.max(1, paperTotalEquity)
      : Math.max(1, liveExposureUsdt);

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Wallet className="h-5 w-5 text-cyan" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">{t('live.portfolioTitle')}</h2>
            <p className="text-xs text-mute">
              Strict separation between Paper virtual capital and Real MEXC spot holdings.
            </p>
          </div>
        </div>
        <Segmented<'real' | 'paper'>
          ariaLabel={t('live.portfolioTitle')}
          value={mode}
          onChange={setMode}
          options={[
            { value: 'real', label: t('live.realTab') },
            { value: 'paper', label: t('live.paperTab') },
          ]}
        />
      </div>

      {live?.local_host_warning && mode === 'real' && (
        <div className="flex items-start gap-2 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div>{live.local_host_warning}</div>
        </div>
      )}

      {mode === 'paper' ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            label="Paper Total Equity"
            value={`$${(paper?.account.total_equity_usdt ?? 10000).toFixed(2)}`}
            tip="Virtual cash plus open paper positions mark-to-market value"
          />
          <MetricCard
            label="Paper Available Cash"
            value={`$${(paper?.account.available_usdt ?? 10000).toFixed(2)}`}
            tip="Unallocated virtual USDT balance in paper account"
          />
          <MetricCard
            label="Paper Positions Value"
            value={`$${(paper?.account.positions_value_usdt ?? 0).toFixed(2)}`}
            tip="Current market value of open paper holdings"
          />
          <MetricCard
            label="Paper Net PnL (Realized + Unrl)"
            value={`$${((paper?.account.realized_pnl_usdt ?? 0) + (paper?.account.unrealized_pnl_usdt ?? 0)).toFixed(2)}`}
            deltaPct={
              paper?.account.initial_balance_usdt
                ? (((paper.account.realized_pnl_usdt + paper.account.unrealized_pnl_usdt) /
                    paper.account.initial_balance_usdt) *
                  100)
                : 0
            }
            tip="Combined realized and unrealized PnL in isolated paper mode"
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            label="Live Spot Exposure"
            value={`$${liveExposureUsdt.toFixed(2)}`}
            tip="Total mark-to-market value of tracked live spot holdings"
          />
          <MetricCard
            label="Live Realized PnL"
            value={`$${(live?.realized_pnl_usdt ?? 0).toFixed(2)}`}
            tip="Cumulative realized profit or loss across filled live trades"
          />
          <MetricCard
            label="Active Authorizations"
            value={String(live?.authorizations.filter((a) => a.active).length ?? 0)}
            tip="Strategy versions currently authorized for live execution"
          />
          <MetricCard
            label="Exchange API Status"
            value={live?.exchange_credentials_configured ? 'Configured' : 'Read-Only'}
            tip="Whether live MEXC API credentials are configured locally"
          />
        </div>
      )}

      <Panel
        title={mode === 'paper' ? `${t('live.paperTab')} — Allocation` : `${t('live.realTab')} — Allocation`}
        actions={<span className="text-xs text-mute">{activePositions.length} open positions</span>}
      >
        {activePositions.length === 0 ? (
          <p className="p-4 text-xs text-mute">
            {mode === 'paper'
              ? '100% Cash (USDT) — No open paper holdings yet.'
              : 'No tracked live spot holdings yet.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-start text-xs">
              <thead className="border-b border-line bg-surface text-mute">
                <tr>
                  <th className="px-3 py-2 text-start">{t('mkt.pair')}</th>
                  <th className="px-3 py-2 text-end">Qty</th>
                  <th className="px-3 py-2 text-end">Entry Price</th>
                  <th className="px-3 py-2 text-end">Mark Price</th>
                  <th className="px-3 py-2 text-end">Market Value</th>
                  <th className="px-3 py-2 text-end">Weight %</th>
                  <th className="px-3 py-2 text-end">Unrealized PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {activePositions.map((pos) => {
                  const weightPct = Math.min(100, (pos.market_value_usdt / activeTotalValue) * 100);
                  return (
                    <tr key={pos.symbol}>
                      <td className="num px-3 py-2 font-semibold">{pos.symbol}</td>
                      <td className="num px-3 py-2 text-end">{pos.qty.toFixed(6)}</td>
                      <td className="num px-3 py-2 text-end">{fmtPrice(pos.avg_entry_price)}</td>
                      <td className="num px-3 py-2 text-end">{fmtPrice(pos.mark_price)}</td>
                      <td className="num px-3 py-2 text-end">${fmtPrice(pos.market_value_usdt)}</td>
                      <td className="num px-3 py-2 text-end">
                        <div className="inline-flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface">
                            <div
                              className="h-full bg-cyan"
                              style={{ width: `${Math.max(2, Math.round(weightPct))}%` }}
                            />
                          </div>
                          <span>{weightPct.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td
                        className={`num px-3 py-2 text-end font-medium ${
                          pos.unrealized_pnl_usdt >= 0 ? 'text-bull' : 'text-bear'
                        }`}
                      >
                        ${pos.unrealized_pnl_usdt.toFixed(2)} ({pos.unrealized_pnl_pct.toFixed(2)}%)
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
