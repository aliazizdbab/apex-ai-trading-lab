import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { MOBILE_TABS, MORE_ICON, NAV_GROUPS } from '@/config/navigation';
import { useT } from '@/i18n/useT';
import { ResponsiveDrawer } from '@/ui/ResponsiveDrawer';
import { GlobalSearch } from './GlobalSearch';

export function MobileNavigation() {
  const t = useT();
  const [moreOpen, setMoreOpen] = useState(false);
  const MoreIcon = MORE_ICON;
  const tabBase = 'flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 text-[11px] transition-colors';

  return (
    <>
      <nav
        aria-label={t('app.name')}
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-panel pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        {MOBILE_TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <NavLink
              key={tab.id}
              to={tab.path}
              end={tab.path === '/'}
              className={({ isActive }) => `${tabBase} ${isActive ? 'text-cyan' : 'text-mute'}`}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span className="max-w-full truncate px-1">{t(tab.labelKey)}</span>
            </NavLink>
          );
        })}
        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={moreOpen}
          className={`${tabBase} ${moreOpen ? 'text-cyan' : 'text-mute'}`}
        >
          <MoreIcon className="h-5 w-5" aria-hidden="true" />
          <span>{t('mobile.more')}</span>
        </button>
      </nav>

      <ResponsiveDrawer open={moreOpen} onClose={() => setMoreOpen(false)} title={t('header.menu')}>
        <GlobalSearch onNavigate={() => setMoreOpen(false)} className="mb-4" />
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="mb-4">
            <p className="pb-1 text-[11px] font-semibold uppercase tracking-wider text-mute">{t(group.labelKey)}</p>
            <ul>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.id}>
                    <NavLink
                      to={item.path}
                      end={item.path === '/'}
                      onClick={() => setMoreOpen(false)}
                      className={({ isActive }) =>
                        `flex min-h-[44px] items-center gap-3 rounded border-s-2 px-2 text-sm ${
                          isActive ? 'border-cyan bg-elevated' : 'border-transparent text-mute'
                        }`
                      }
                    >
                      <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
                      {t(item.labelKey)}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </ResponsiveDrawer>
    </>
  );
}
