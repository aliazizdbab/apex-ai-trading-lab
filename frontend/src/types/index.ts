export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting' | 'error';

export interface MarketRow {
  symbol: string; // e.g. "BTC/USDT"
  last: number;
  change24h: number; // percent
  volume24h: number; // quote volume
  high: number;
  low: number;
  status: 'trading' | 'halted';
}

export interface Candle {
  time: number; // UTC seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
