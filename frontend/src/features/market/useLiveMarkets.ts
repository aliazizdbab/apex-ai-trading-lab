import { useQuery } from '@tanstack/react-query';
import { DEMO_MARKETS } from '@/features/market/demoData';
import { fetchMarketTickers, type MarketTickerRow } from '@/services/api';
import type { MarketRow } from '@/types';

export function useLiveMarkets() {
  const query = useQuery({
    queryKey: ['mexc-tickers'],
    queryFn: fetchMarketTickers,
    refetchInterval: 15_000,
    retry: 1,
  });

  const liveItems: MarketTickerRow[] = query.data?.items ?? [];
  const isLive = liveItems.length > 0 && !query.isError;
  const rows: MarketRow[] = isLive ? liveItems : DEMO_MARKETS;

  return {
    rows,
    liveItems,
    isLive,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}
