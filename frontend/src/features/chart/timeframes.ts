export interface Timeframe {
  id: string;
  seconds: number;
}

/**
 * The 15 timeframes required by the specification.
 * NOTE: "1M" uses a fixed 30-day step here only for demo candles. Real calendar-month and
 * week boundaries (UTC) are implemented with the candle aggregation in Phase 3.
 */
export const TIMEFRAMES: Timeframe[] = [
  { id: '1m', seconds: 60 },
  { id: '3m', seconds: 180 },
  { id: '5m', seconds: 300 },
  { id: '15m', seconds: 900 },
  { id: '30m', seconds: 1800 },
  { id: '1h', seconds: 3600 },
  { id: '2h', seconds: 7200 },
  { id: '4h', seconds: 14400 },
  { id: '6h', seconds: 21600 },
  { id: '8h', seconds: 28800 },
  { id: '12h', seconds: 43200 },
  { id: '1D', seconds: 86400 },
  { id: '3D', seconds: 259200 },
  { id: '1W', seconds: 604800 },
  { id: '1M', seconds: 2592000 },
];
