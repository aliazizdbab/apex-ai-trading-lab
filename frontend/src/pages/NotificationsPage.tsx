import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck, Lock } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useT } from '@/i18n/useT';
import {
  fetchAuthStatus,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/services/api';
import { EmptyState } from '@/ui/EmptyState';
import { Panel } from '@/ui/Panel';

const levelStyle: Record<string, string> = {
  info: 'border-cyan/30 bg-cyan/10 text-cyan',
  warning: 'border-amber/30 bg-amber/10 text-amber',
  error: 'border-bear/30 bg-bear/10 text-bear',
};

export function NotificationsPage() {
  const t = useT();
  const queryClient = useQueryClient();

  const { data: authStatus, isLoading: authLoading } = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    retry: false,
  });

  const authenticated = Boolean(authStatus?.authenticated);

  const { data, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: listNotifications,
    enabled: authenticated,
    retry: false,
  });

  const markReadMut = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  const markAllMut = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  if (authLoading) {
    return <p className="text-sm text-mute">{t('common.loading')}</p>;
  }

  if (!authenticated) {
    return (
      <div className="mx-auto max-w-2xl">
        <Panel>
          <EmptyState
            icon={Lock}
            title={t('notif.authRequiredTitle')}
            body={t('notif.authRequiredBody')}
          >
            <Link
              to="/settings"
              className="mt-2 inline-flex min-h-[38px] items-center rounded bg-cyan px-4 text-sm font-medium text-bg hover:opacity-90"
            >
              {t('notif.goToSettings')}
            </Link>
          </EmptyState>
        </Panel>
      </div>
    );
  }

  const items = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">{t('notif.title')}</h2>
          <span className="rounded border border-line bg-surface px-2 py-0.5 text-xs text-mute">
            {t('notif.unread', { count: unreadCount })}
          </span>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={() => markAllMut.mutate()}
            disabled={markAllMut.isPending}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded border border-line bg-surface px-3 text-xs font-medium hover:border-cyan"
          >
            <CheckCheck className="h-4 w-4 text-cyan" aria-hidden="true" />
            {t('notif.markAll')}
          </button>
        )}
      </div>

      <Panel>
        {isLoading ? (
          <p className="p-4 text-sm text-mute">{t('common.loading')}</p>
        ) : items.length === 0 ? (
          <EmptyState icon={Bell} title={t('notif.empty')} />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((item) => (
              <li
                key={item.id}
                className={`flex flex-wrap items-start justify-between gap-3 p-4 ${
                  item.is_read ? 'opacity-70' : 'bg-surface/40'
                }`}
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase ${
                        levelStyle[item.level] ?? levelStyle.info
                      }`}
                    >
                      {item.level}
                    </span>
                    <span className="text-xs text-mute">{item.category}</span>
                    <span className="text-xs text-mute tabular-nums">
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm font-semibold">{item.title}</p>
                  <p className="text-xs text-mute">{item.body}</p>
                </div>
                {!item.is_read ? (
                  <button
                    type="button"
                    onClick={() => markReadMut.mutate(item.id)}
                    className="min-h-[32px] shrink-0 rounded border border-line bg-surface px-2.5 text-xs hover:border-cyan"
                  >
                    {t('notif.markRead')}
                  </button>
                ) : (
                  <span className="text-xs text-mute">{t('notif.read')}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
