import { describe, expect, it } from 'vitest';
import { generateDemoCandles, seedFromString } from './demoCandles';
import { TIMEFRAMES } from './timeframes';

const base = { count: 200, stepSeconds: 900, seed: 7, startPrice: 100, endTime: 1_700_000_000 };

describe('generateDemoCandles', () => {
  it('is deterministic for the same seed', () => {
    expect(generateDemoCandles(base)).toEqual(generateDemoCandles(base));
  });

  it('differs for another seed', () => {
    expect(generateDemoCandles({ ...base, seed: 8 })).not.toEqual(generateDemoCandles(base));
  });

  it('produces valid OHLC candles', () => {
    for (const c of generateDemoCandles(base)) {
      expect(c.high).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
      expect(c.low).toBeLessThanOrEqual(Math.min(c.open, c.close));
      expect(c.low).toBeGreaterThan(0);
      expect(c.volume).toBeGreaterThan(0);
    }
  });

  it('has strictly increasing, evenly spaced times ending at endTime', () => {
    const candles = generateDemoCandles(base);
    expect(candles).toHaveLength(base.count);
    expect(candles[candles.length - 1]!.time).toBe(base.endTime);
    for (let i = 1; i < candles.length; i++) {
      expect(candles[i]!.time - candles[i - 1]!.time).toBe(base.stepSeconds);
    }
  });
});

describe('timeframes', () => {
  it('defines the 15 required timeframes in ascending order', () => {
    expect(TIMEFRAMES.map((t) => t.id)).toEqual([
      '1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1D', '3D', '1W', '1M',
    ]);
    for (let i = 1; i < TIMEFRAMES.length; i++) {
      expect(TIMEFRAMES[i]!.seconds).toBeGreaterThan(TIMEFRAMES[i - 1]!.seconds);
    }
  });

  it('hashes strings deterministically', () => {
    expect(seedFromString('BTC/USDT')).toBe(seedFromString('BTC/USDT'));
    expect(seedFromString('BTC/USDT')).not.toBe(seedFromString('ETH/USDT'));
  });
});
