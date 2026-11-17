import type { Candle } from '@/types';

/** DEMO DATA ONLY: deterministic pseudo-random candles used to preview the chart UI. */

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seedFromString(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export interface DemoCandleOptions {
  count: number;
  stepSeconds: number;
  seed: number;
  startPrice: number;
  /** Open time (UTC seconds) of the last candle. */
  endTime: number;
}

export function generateDemoCandles(opts: DemoCandleOptions): Candle[] {
  const rand = mulberry32(opts.seed);
  const decimals = opts.startPrice < 1 ? 6 : 2;
  const round = (v: number) => Number(v.toFixed(decimals));
  const candles: Candle[] = [];
  let price = opts.startPrice;

  for (let i = 0; i < opts.count; i++) {
    const time = opts.endTime - (opts.count - 1 - i) * opts.stepSeconds;
    const open = price;
    const close = Math.max(open * 0.2, open + (rand() - 0.5) * 0.012 * open);
    const high = Math.max(open, close) + rand() * 0.004 * open;
    const low = Math.max(open * 0.1, Math.min(open, close) - rand() * 0.004 * open);
    candles.push({
      time,
      open: round(open),
      high: round(high),
      low: round(low),
      close: round(close),
      volume: Math.round(50 + rand() * 950),
    });
    price = close;
  }
  return candles;
}
