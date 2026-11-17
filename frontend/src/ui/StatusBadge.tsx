import type { TKey } from '@/i18n/en';
import { useT } from '@/i18n/useT';
import type { ConnectionState } from '@/types';

const dot: Record<ConnectionState, string> = {
  connected: 'bg-bull',
  disconnected: 'bg-mute',
  reconnecting: 'bg-amber animate-pulse',
  error: 'bg-bear',
};

const stateKey: Record<ConnectionState, TKey> = {
  connected: 'status.connected',
  disconnected: 'status.disconnected',
  reconnecting: 'status.reconnecting',
  error: 'status.error',
};

interface Props {
  label: string;
  state: ConnectionState;
  title?: string;
}

export function StatusBadge({ label, state, title }: Props) {
  const t = useT();
  const stateText = t(stateKey[state]);
  return (
    <span
      title={title ? `${label}: ${stateText}. ${title}` : `${label}: ${stateText}`}
      className="inline-flex min-h-[28px] items-center gap-1.5 rounded border border-line bg-surface px-2 text-[11px] font-medium"
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot[state]}`} aria-hidden="true" />
      <span>{label}</span>
      <span className="hidden text-mute 2xl:inline">{stateText}</span>
      <span className="sr-only">{stateText}</span>
    </span>
  );
}
