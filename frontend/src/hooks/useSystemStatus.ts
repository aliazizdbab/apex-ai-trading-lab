import type { ConnectionState } from '@/types';

export interface SystemStatus {
  mexc: ConnectionState;
  ai: ConnectionState;
  engine: ConnectionState;
}

/**
 * Phase 1: no backend exists, so every service is honestly reported as disconnected.
 * Phase 2/3 replace this with real health data from the API. Never fake a connected state.
 */
export function useSystemStatus(): SystemStatus {
  return { mexc: 'disconnected', ai: 'disconnected', engine: 'disconnected' };
}
