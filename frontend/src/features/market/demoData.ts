import type { MarketRow } from '@/types';

/**
 * DEMO DATA ONLY. These numbers are invented to preview the interface.
 * They are not market data. Real data arrives with the MEXC integration (Phase 3).
 */
export const DEMO_MARKETS: MarketRow[] = [
  { symbol: 'BTC/USDT', last: 64250.5, change24h: 1.84, volume24h: 812_400_000, high: 65010, low: 63120.4, status: 'trading' },
  { symbol: 'ETH/USDT', last: 3120.25, change24h: -0.62, volume24h: 421_300_000, high: 3188, low: 3075.1, status: 'trading' },
  { symbol: 'SOL/USDT', last: 148.9, change24h: 3.41, volume24h: 198_700_000, high: 151.2, low: 141.8, status: 'trading' },
  { symbol: 'BNB/USDT', last: 585.3, change24h: 0.27, volume24h: 96_500_000, high: 590, low: 579.4, status: 'trading' },
  { symbol: 'XRP/USDT', last: 0.5234, change24h: -1.95, volume24h: 88_200_000, high: 0.5412, low: 0.5171, status: 'trading' },
  { symbol: 'ADA/USDT', last: 0.4518, change24h: 2.12, volume24h: 41_900_000, high: 0.4602, low: 0.4401, status: 'trading' },
  { symbol: 'DOGE/USDT', last: 0.1284, change24h: -3.08, volume24h: 67_400_000, high: 0.1349, low: 0.1262, status: 'trading' },
  { symbol: 'LINK/USDT', last: 14.62, change24h: 0.91, volume24h: 29_800_000, high: 14.9, low: 14.31, status: 'trading' },
  { symbol: 'AVAX/USDT', last: 35.74, change24h: -0.15, volume24h: 24_100_000, high: 36.4, low: 35.2, status: 'trading' },
  { symbol: 'TON/USDT', last: 6.81, change24h: 4.27, volume24h: 18_700_000, high: 6.95, low: 6.52, status: 'halted' },
];

export const DEMO_METRICS = {
  portfolio: { value: 10482.35, deltaPct: 1.12, spark: [100, 101, 100.4, 102, 101.6, 103, 102.4, 104.8] },
  availableUsdt: { value: 6120.0, deltaPct: 0, spark: [6120, 6120, 6120, 6120, 6120, 6120] },
  unrealized: { value: 142.6, deltaPct: 0.9, spark: [0, 20, 15, 60, 45, 110, 142] },
  realized: { value: 339.75, deltaPct: 3.4, spark: [0, 40, 40, 120, 180, 260, 340] },
  todayReturn: { value: 1.12, deltaPct: 1.12, spark: [0, 0.2, 0.1, 0.6, 0.5, 0.9, 1.1] },
  activeStrategies: { value: 0, spark: [0, 0, 0, 0] },
  openPositions: { value: 0, spark: [0, 0, 0, 0] },
};
