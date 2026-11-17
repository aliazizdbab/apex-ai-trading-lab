import type { MarketRow } from '@/types';

export type SortKey = 'symbol' | 'last' | 'change24h' | 'volume24h';
export type SortDir = 'asc' | 'desc';

export function filterMarkets(
  rows: MarketRow[],
  query: string,
  favorites: string[],
  onlyFavorites: boolean,
): MarketRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter(
    (r) => (!onlyFavorites || favorites.includes(r.symbol)) && (q === '' || r.symbol.toLowerCase().includes(q)),
  );
}

export function sortMarkets(rows: MarketRow[], key: SortKey, dir: SortDir): MarketRow[] {
  const m = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => (key === 'symbol' ? a.symbol.localeCompare(b.symbol) * m : (a[key] - b[key]) * m));
}
