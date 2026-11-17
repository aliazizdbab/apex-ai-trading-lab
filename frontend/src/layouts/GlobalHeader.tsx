import { Bell, Moon, Settings, Sun, User } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ALL_NAV_ITEMS } from '@/config/navigation';
import { useClickOutside } from '@/hooks/useClickOutside';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { useT } from '@/i18n/useT';
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
  const setLang = useUiStore((s) => s.setLang);

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  useClickOutside(menuRef, closeMenu);

  const current = ALL_NAV_ITEMS.find((i) => i.path === pathname);
  const title = current ? t(current.labelKey) : t('common.notFoundTitle');
  const ThemeIcon = theme === 'dark' ? Sun : Moon;
  const iconButton =
    'flex h-11 w-11 shrink-0 items-center justify-center rounded text-mute hover:bg-surface hover:text-ink sm:h-9 sm:w-9';

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line bg-panel px-3 sm:gap-3 sm:px-4">
      <div className="lg:hidden">
        <Logo showText={false} />
      </div>
      <h1 className="min-w-0 truncate text-sm font-semibold sm:text-base">{title}</h1>

      <div className="ms-auto flex items-center gap-1.5 sm:gap-2">
        <div className="hidden items-center gap-1.5 md:flex">
          <StatusBadge label={t('status.mexc')} state={status.mexc} title={t('status.notWired')} />
          <StatusBadge label={t('status.ai')} state={status.ai} title={t('status.notWired')} />
          <StatusBadge label={t('status.engine')} state={status.engine} title={t('status.notWired')} />
        </div>

        <GlobalSearch className="hidden w-56 lg:block xl:w-72" />

        <Link to="/notifications" aria-label={t('header.notifications')} title={t('header.notifications')} className={iconButton}>
          <Bell className="h-[18px] w-[18px]" aria-hidden="true" />
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
