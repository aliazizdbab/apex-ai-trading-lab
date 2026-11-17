import { ArrowDown, ArrowUp, CandlestickChart, Star } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useT } from '@/i18n/useT';
import { useUiStore } from '@/stores/uiStore';
import type { MarketRow } from '@/types';
import { EmptyState } from '@/ui/EmptyState';
import { fmtCompact, fmtPct, fmtPrice } from '@/utils/format';
import { filterMarkets, sortMarkets, type SortDir, type SortKey } from './marketUtils';

interface Props {
  rows: MarketRow[];
}

export function MarketTable({ rows }: Props) {
  const t = useT();
  const navigate = useNavigate();
  const favorites = useUiStore((s) => s.favorites);
  const toggleFavorite = useUiStore((s) => s.toggleFavorite);

  const [query, setQuery] = useState('');
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('volume24h');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const visible = useMemo(
    () => sortMarkets(filterMarkets(rows, query, favorites, onlyFavorites), sortKey, sortDir),
    [rows, query, favorites, onlyFavorites, sortKey, sortDir],
  );

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir(key === 'symbol' ? 'asc' : 'desc');
    }
  };

  const header = (key: SortKey, label: string, align: 'start' | 'end' = 'end') => {
    const active = key === sortKey;
    const Arrow = sortDir === 'asc' ? ArrowUp : ArrowDown;
    return (
      <th scope="col" aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} className="px-3 py-2 font-medium">
        <button
          type="button"
          onClick={() => sortBy(key)}
          className={`inline-flex min-h-[32px] items-center gap-1 hover:text-ink ${align === 'end' ? 'float-end' : ''}`}
        >
          {label}
          {active && <Arrow className="h-3 w-3" aria-hidden="true" />}
        </button>
      </th>
    );
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('mkt.search')}
          aria-label={t('mkt.search')}
          className="h-11 min-w-0 flex-1 rounded-md border border-line bg-surface px-3 text-sm placeholder:text-mute sm:h-9 sm:max-w-xs"
        />
        <label className="flex min-h-[44px] cursor-pointer items-center gap-2 text-xs text-mute sm:min-h-[36px]">
          <input type="checkbox" checked={onlyFavorites} onChange={(e) => setOnlyFavorites(e.target.checked)} className="h-4 w-4 accent-cyan" />
          {t('mkt.onlyFavorites')}
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState title={t('mkt.noResults')} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-xs text-mute">
              <tr className="border-b border-line text-start">
                <th scope="col" className="sticky start-0 z-10 bg-panel px-3 py-2 text-start font-medium">
                  <button type="button" onClick={() => sortBy('symbol')} className="inline-flex min-h-[32px] items-center gap-1 hover:text-ink">
                    {t('mkt.pair')}
                    {sortKey === 'symbol' &&
                      (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" aria-hidden="true" /> : <ArrowDown className="h-3 w-3" aria-hidden="true" />)}
                  </button>
                </th>
                {header('last', t('mkt.last'))}
                {header('change24h', t('mkt.change'))}
                {header('volume24h', t('mkt.volume'))}
                <th scope="col" className="px-3 py-2 text-end font-medium">{t('mkt.high')}</th>
                <th scope="col" className="px-3 py-2 text-end font-medium">{t('mkt.low')}</th>
                <th scope="col" className="px-3 py-2 text-start font-medium">{t('mkt.status')}</th>
                <th scope="col" className="px-3 py-2"><span className="sr-only">{t('mkt.openChart')}</span></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => {
                const fav = favorites.includes(r.symbol);
                return (
                  <tr key={r.symbol} className="border-b border-line/60 hover:bg-surface/60">
                    <td className="sticky start-0 z-10 bg-panel px-3 py-1">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => toggleFavorite(r.symbol)}
                          aria-pressed={fav}
                          aria-label={`${t('mkt.toggleFav')}: ${r.symbol}`}
                          className="flex h-11 w-9 items-center justify-center sm:h-8"
                        >
                          <Star className={`h-4 w-4 ${fav ? 'fill-amber text-amber' : 'text-mute'}`} aria-hidden="true" />
                        </button>
                        <span className="num font-semibold">{r.symbol}</span>
                      </div>
                    </td>
                    <td className="num px-3 py-1 text-end">{fmtPrice(r.last)}</td>
                    <td className={`num px-3 py-1 text-end font-medium ${r.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>{fmtPct(r.change24h)}</td>
                    <td className="num px-3 py-1 text-end">{fmtCompact(r.volume24h)}</td>
                    <td className="num px-3 py-1 text-end text-mute">{fmtPrice(r.high)}</td>
                    <td className="num px-3 py-1 text-end text-mute">{fmtPrice(r.low)}</td>
                    <td className="px-3 py-1 text-xs text-mute">{r.status === 'trading' ? t('mkt.trading') : t('mkt.halted')}</td>
                    <td className="px-3 py-1 text-end">
                      <button
                        type="button"
                        onClick={() => navigate(`/terminal?symbol=${encodeURIComponent(r.symbol)}`)}
                        aria-label={`${t('mkt.openChart')}: ${r.symbol}`}
                        title={t('mkt.openChart')}
                        className="inline-flex h-11 w-11 items-center justify-center rounded text-mute hover:bg-elevated hover:text-cyan sm:h-8 sm:w-8"
                      >
                        <CandlestickChart className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
