import { useQuery } from '@tanstack/react-query';
import { Bell, BookOpen, Bot, Download, Moon, Settings, Sun, User } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ALL_NAV_ITEMS } from '@/config/navigation';
import { useClickOutside } from '@/hooks/useClickOutside';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { useT } from '@/i18n/useT';
import { checkGithubUpdates, fetchAuthStatus, listNotifications } from '@/services/api';
import { useUiStore, type Lang } from '@/stores/uiStore';
import { Logo } from '@/ui/Logo';
import { StatusBadge } from '@/ui/StatusBadge';
import { GlobalSearch } from './GlobalSearch';

export function GlobalHeader() {
  const t = useT();
  const { pathname } = useLocation();
  const status = useSystemStatus();
  const theme = useUiStore((s) => s.theme);
  const lang = useUiStore((s) => s.lang);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const toggleCopilot = useUiStore((s) => s.toggleCopilot);
  const copilotOpen = useUiStore((s) => s.copilotOpen);
  const setLang = useUiStore((s) => s.setLang);

  const { data: authStatus } = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    retry: false,
  });

  const { data: notifData } = useQuery({
    queryKey: ['notifications'],
    queryFn: listNotifications,
    enabled: Boolean(authStatus?.authenticated),
    refetchInterval: 15_000,
    retry: false,
  });

  const unreadCount = notifData?.unread_count ?? 0;

  const { data: updateInfo } = useQuery({
    queryKey: ['github-update-check'],
    queryFn: checkGithubUpdates,
    staleTime: 300_000,
    refetchInterval: 600_000,
    retry: false,
  });

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  useClickOutside(menuRef, closeMenu);

  const current = ALL_NAV_ITEMS.find((i) => i.path === pathname);
  const title = current ? t(current.labelKey) : t('common.notFoundTitle');
  const ThemeIcon = theme === 'dark' ? Sun : Moon;
  const iconButton =
    'relative flex h-9 w-9 shrink-0 items-center justify-center rounded text-mute hover:bg-surface hover:text-ink';

  return (
    <header className="flex h-14 w-full min-w-0 shrink-0 items-center gap-1.5 border-b border-line bg-panel px-2.5 sm:gap-3 sm:px-4">
      <div className="lg:hidden">
        <Logo showText={false} />
      </div>
      <h1 className="min-w-0 truncate text-sm font-semibold sm:text-base">{title}</h1>

      <div className="ms-auto flex min-w-0 items-center gap-1 sm:gap-2">
        <div className="hidden items-center gap-1.5 md:flex">
          <StatusBadge
            label={t('status.mexc')}
            state={status.mexc}
            title={status.mexc === 'connected' ? t('status.mexcConnected') : t('status.mexcPlanned')}
          />
          <StatusBadge label={t('status.ai')} state={status.ai} title={t('status.aiPlanned')} />
          <StatusBadge
            label={t('status.engine')}
            state={status.engine}
            title={status.engine === 'connected' ? t('status.engineConnected') : t('status.notWired')}
          />
        </div>

        <GlobalSearch className="hidden w-56 lg:block xl:w-72" />

        <Link
          to="/settings#updates"
          title={t('upd.title')}
          className={`hidden h-9 shrink-0 items-center gap-1 rounded border px-2 text-[11px] font-medium transition md:inline-flex ${
            updateInfo?.update_available
              ? 'border-warn/60 bg-warn/15 text-warn'
              : 'border-line bg-surface text-mute hover:border-cyan/60 hover:text-ink'
          }`}
        >
          <Download className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="num">
            v{updateInfo?.current_version ?? '1.1.0'}
            {updateInfo?.update_available ? ` → ${updateInfo.latest_tag}` : ''}
          </span>
        </Link>

        <Link
          to="/guide"
          aria-label={t('nav.guide')}
          title={t('nav.guide')}
          className={iconButton}
        >
          <BookOpen className="h-[18px] w-[18px] text-cyan" aria-hidden="true" />
        </Link>

        <button
          type="button"
          onClick={toggleCopilot}
          aria-pressed={copilotOpen}
          title={t('copilot.subtitle')}
          className={`flex h-9 shrink-0 items-center gap-1.5 rounded border px-2.5 text-xs font-medium transition ${
            copilotOpen
              ? 'border-cyan bg-cyan/15 text-cyan'
              : 'border-line bg-surface text-ink hover:border-cyan/60'
          }`}
        >
          <Bot className="h-4 w-4 text-cyan" aria-hidden="true" />
          <span className="hidden sm:inline">{t('copilot.button')}</span>
        </button>

        <Link to="/notifications" aria-label={t('header.notifications')} title={t('header.notifications')} className={iconButton}>
          <Bell className="h-[18px] w-[18px]" aria-hidden="true" />
          {unreadCount > 0 && (
            <span className="absolute end-1.5 top-1.5 h-2 w-2 rounded-full bg-cyan" aria-hidden="true" />
          )}
        </Link>

        <button type="button" onClick={toggleTheme} aria-label={t('header.toggleTheme')} title={t('header.toggleTheme')} className={iconButton}>
          <ThemeIcon className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>

        <select
          value={lang}
          onChange={(e) => setLang(e.target.value as Lang)}
          aria-label={t('header.language')}
          className="h-11 rounded border border-line bg-surface px-1.5 text-xs sm:h-9"
        >
          <option value="en">EN</option>
          <option value="ar">عربي</option>
        </select>

        <div ref={menuRef} className="relative hidden sm:block">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={t('header.profile')}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className={iconButton}
          >
            <User className="h-[18px] w-[18px]" aria-hidden="true" />
          </button>
          {menuOpen && (
            <div role="menu" className="absolute end-0 top-full z-40 mt-1 w-48 animate-fadeIn rounded-md border border-line bg-elevated py-1 shadow-lg">
              {authStatus?.user && (
                <div className="border-b border-line px-3 py-2 text-xs text-mute">
                  <div className="truncate font-medium text-ink">{authStatus.user.display_name}</div>
                  <div className="truncate">{authStatus.user.email}</div>
                </div>
              )}
              <Link
                to="/settings"
                role="menuitem"
                onClick={closeMenu}
                className="flex min-h-[36px] items-center gap-2 px-3 text-sm hover:bg-surface"
              >
                <Settings className="h-4 w-4 text-mute" aria-hidden="true" />
                {t('nav.settings')}
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
