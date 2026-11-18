import { CandlestickChart, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLiveMarkets } from '@/features/market/useLiveMarkets';
import { useT } from '@/i18n/useT';
import { DemoBadge } from '@/ui/DemoBadge';
import { EmptyState } from '@/ui/EmptyState';
import { LiveBadge } from '@/ui/LiveBadge';
import { Panel } from '@/ui/Panel';
import { fmtCompact, fmtPct, fmtPrice } from '@/utils/format';

export function LiveMarketPage() {
  const t = useT();
  const navigate = useNavigate();
  const { liveItems, rows, isLive, isLoading, refetch } = useLiveMarkets();
  const [query, setQuery] = useState('');

  const items = useMemo(() => {
    const q = query.trim().toUpperCase();
    const list = liveItems.length > 0
      ? liveItems
      : rows.map((r) => ({ ...r, bid: r.last, ask: r.last, mexc_symbol: r.symbol.replace('/', ''), baseVolume24h: 0 }));
    if (!q) return list;
    return list.filter((r) => r.symbol.toUpperCase().includes(q));
  }, [liveItems, rows, query]);

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{t('liveMkt.title')}</h2>
          {isLive ? <LiveBadge /> : <DemoBadge />}
        </div>
        <button
          type="button"
          onClick={() => void refetch()}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium hover:border-cyan"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
          {t('common.refresh')}
        </button>
      </div>

      <Panel>
        <div className="border-b border-line p-3">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('mkt.search')}
            aria-label={t('mkt.search')}
            className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm placeholder:text-mute sm:max-w-xs"
          />
        </div>
        {items.length === 0 ? (
          <EmptyState title={t('mkt.noResults')} />
        ) : (
          <div className="w-full max-w-full overflow-x-auto">
            <table className="w-full text-xs sm:text-sm">
              <thead className="border-b border-line text-xs text-mute">
                <tr>
                  <th className="px-2 py-2 text-start font-medium sm:px-3">{t('mkt.pair')}</th>
                  <th className="px-2 py-2 text-end font-medium sm:px-3">{t('mkt.last')}</th>
                  <th className="px-2 py-2 text-end font-medium sm:px-3">{t('mkt.change')}</th>
                  <th className="hidden px-3 py-2 text-end font-medium md:table-cell">{t('liveMkt.bid')}</th>
                  <th className="hidden px-3 py-2 text-end font-medium md:table-cell">{t('liveMkt.ask')}</th>
                  <th className="hidden px-3 py-2 text-end font-medium lg:table-cell">{t('liveMkt.spread')}</th>
                  <th className="hidden px-3 py-2 text-end font-medium sm:table-cell">{t('mkt.volume')}</th>
                  <th className="px-2 py-2 text-end font-medium sm:px-3">{t('liveMkt.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {items.map((r) => {
                  const spreadPct = r.ask > 0 && r.bid > 0 ? ((r.ask - r.bid) / r.ask) * 100 : 0;
                  return (
                    <tr key={r.symbol} className="hover:bg-surface/60">
                      <td className="num whitespace-nowrap px-2 py-2 font-semibold sm:px-3">{r.symbol}</td>
                      <td className="num whitespace-nowrap px-2 py-2 text-end sm:px-3">{fmtPrice(r.last)}</td>
                      <td className={`num whitespace-nowrap px-2 py-2 text-end font-medium sm:px-3 ${r.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>
                        {fmtPct(r.change24h)}
                      </td>
                      <td className="num hidden whitespace-nowrap px-3 py-2 text-end text-bull md:table-cell">{fmtPrice(r.bid)}</td>
                      <td className="num hidden whitespace-nowrap px-3 py-2 text-end text-bear md:table-cell">{fmtPrice(r.ask)}</td>
                      <td className="num hidden whitespace-nowrap px-3 py-2 text-end text-mute lg:table-cell">{spreadPct.toFixed(3)}%</td>
                      <td className="num hidden whitespace-nowrap px-3 py-2 text-end sm:table-cell">{fmtCompact(r.volume24h)}</td>
                      <td className="px-2 py-2 text-end sm:px-3">
                        <button
                          type="button"
                          onClick={() => navigate(`/terminal?symbol=${encodeURIComponent(r.symbol)}`)}
                          className="inline-flex min-h-[32px] items-center gap-1 rounded border border-line bg-surface px-2 text-xs hover:border-cyan hover:text-cyan sm:px-2.5"
                        >
                          <CandlestickChart className="h-3.5 w-3.5" aria-hidden="true" />
                          <span className="hidden sm:inline">{t('mkt.openChart')}</span>
                        </button>
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
