import { describe, expect, it } from 'vitest';
import { DEMO_MARKETS } from './demoData';
import { filterMarkets, sortMarkets } from './marketUtils';

describe('filterMarkets', () => {
  it('matches the query case-insensitively', () => {
    const out = filterMarkets(DEMO_MARKETS, 'btc', [], false);
    expect(out.map((r) => r.symbol)).toEqual(['BTC/USDT']);
  });

  it('returns everything for an empty query', () => {
    expect(filterMarkets(DEMO_MARKETS, '  ', [], false)).toHaveLength(DEMO_MARKETS.length);
  });

  it('restricts to favorites when requested', () => {
    const out = filterMarkets(DEMO_MARKETS, '', ['ETH/USDT', 'SOL/USDT'], true);
    expect(out.map((r) => r.symbol).sort()).toEqual(['ETH/USDT', 'SOL/USDT']);
  });
});

describe('sortMarkets', () => {
  it('sorts numerically descending without mutating the input', () => {
    const copy = [...DEMO_MARKETS];
    const out = sortMarkets(DEMO_MARKETS, 'change24h', 'desc');
    expect(DEMO_MARKETS).toEqual(copy);
    for (let i = 1; i < out.length; i++) {
      expect(out[i - 1]!.change24h).toBeGreaterThanOrEqual(out[i]!.change24h);
    }
  });

  it('sorts by symbol ascending', () => {
    const out = sortMarkets(DEMO_MARKETS, 'symbol', 'asc').map((r) => r.symbol);
    expect(out).toEqual([...out].sort((a, b) => a.localeCompare(b)));
  });
});
