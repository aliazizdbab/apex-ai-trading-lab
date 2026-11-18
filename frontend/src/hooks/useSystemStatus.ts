import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from '@/services/api';
import type { ConnectionState } from '@/types';

export interface SystemStatus {
  mexc: ConnectionState;
  ai: ConnectionState;
  engine: ConnectionState;
}

const DISCONNECTED: SystemStatus = {
  mexc: 'disconnected',
  ai: 'disconnected',
  engine: 'disconnected',
};

/**
 * Polls `/api/v1/health` so Engine reflects actual backend reachability
 * while MEXC and AI remain honestly disconnected until Phases 3 and 10/14.
 */
export function useSystemStatus(): SystemStatus {
  const { data } = useQuery({
    queryKey: ['system-health'],
    queryFn: fetchHealth,
    refetchInterval: 10_000,
    retry: false,
  });

  if (!data) return DISCONNECTED;
  return {
    engine: data.engine,
    mexc: data.mexc,
    ai: data.ai,
  };
}
