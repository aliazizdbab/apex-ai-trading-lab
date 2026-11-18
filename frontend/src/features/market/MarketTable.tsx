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
        <div className="w-full max-w-full overflow-x-auto">
          <table className="w-full text-xs sm:text-sm">
            <thead className="text-xs text-mute">
              <tr className="border-b border-line text-start">
                <th scope="col" className="px-2 py-2 text-start font-medium sm:px-3">
                  <button type="button" onClick={() => sortBy('symbol')} className="inline-flex min-h-[32px] items-center gap-1 hover:text-ink">
                    {t('mkt.pair')}
                    {sortKey === 'symbol' &&
                      (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" aria-hidden="true" /> : <ArrowDown className="h-3 w-3" aria-hidden="true" />)}
                  </button>
                </th>
                {header('last', t('mkt.last'))}
                {header('change24h', t('mkt.change'))}
                <th scope="col" className="hidden px-3 py-2 text-end font-medium sm:table-cell">
                  <button type="button" onClick={() => sortBy('volume24h')} className="inline-flex min-h-[32px] items-center gap-1 hover:text-ink">
                    {t('mkt.volume')}
                    {sortKey === 'volume24h' &&
                      (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" aria-hidden="true" /> : <ArrowDown className="h-3 w-3" aria-hidden="true" />)}
                  </button>
                </th>
                <th scope="col" className="hidden px-3 py-2 text-end font-medium lg:table-cell">{t('mkt.high')}</th>
                <th scope="col" className="hidden px-3 py-2 text-end font-medium lg:table-cell">{t('mkt.low')}</th>
                <th scope="col" className="hidden px-3 py-2 text-start font-medium md:table-cell">{t('mkt.status')}</th>
                <th scope="col" className="px-2 py-2 sm:px-3"><span className="sr-only">{t('mkt.openChart')}</span></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => {
                const fav = favorites.includes(r.symbol);
                return (
                  <tr key={r.symbol} className="border-b border-line/60 hover:bg-surface/60">
                    <td className="px-2 py-1.5 sm:px-3">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => toggleFavorite(r.symbol)}
                          aria-pressed={fav}
                          aria-label={`${t('mkt.toggleFav')}: ${r.symbol}`}
                          className="flex h-9 w-7 shrink-0 items-center justify-center sm:h-8 sm:w-8"
                        >
                          <Star className={`h-3.5 w-3.5 sm:h-4 sm:w-4 ${fav ? 'fill-amber text-amber' : 'text-mute'}`} aria-hidden="true" />
                        </button>
                        <span className="num whitespace-nowrap font-semibold">{r.symbol}</span>
                      </div>
                    </td>
                    <td className="num whitespace-nowrap px-2 py-1.5 text-end sm:px-3">{fmtPrice(r.last)}</td>
                    <td className={`num whitespace-nowrap px-2 py-1.5 text-end font-medium sm:px-3 ${r.change24h >= 0 ? 'text-bull' : 'text-bear'}`}>{fmtPct(r.change24h)}</td>
                    <td className="num hidden whitespace-nowrap px-3 py-1.5 text-end sm:table-cell">{fmtCompact(r.volume24h)}</td>
                    <td className="num hidden whitespace-nowrap px-3 py-1.5 text-end text-mute lg:table-cell">{fmtPrice(r.high)}</td>
                    <td className="num hidden whitespace-nowrap px-3 py-1.5 text-end text-mute lg:table-cell">{fmtPrice(r.low)}</td>
                    <td className="hidden px-3 py-1.5 text-xs text-mute md:table-cell">{r.status === 'trading' ? t('mkt.trading') : t('mkt.halted')}</td>
                    <td className="px-2 py-1.5 text-end sm:px-3">
                      <button
                        type="button"
                        onClick={() => navigate(`/terminal?symbol=${encodeURIComponent(r.symbol)}`)}
                        aria-label={`${t('mkt.openChart')}: ${r.symbol}`}
                        title={t('mkt.openChart')}
                        className="inline-flex h-9 w-9 items-center justify-center rounded text-mute hover:bg-elevated hover:text-cyan sm:h-8 sm:w-8"
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
