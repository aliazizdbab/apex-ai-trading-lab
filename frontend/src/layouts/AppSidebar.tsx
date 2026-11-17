import { ChevronsLeft, ChevronsRight } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { NAV_GROUPS } from '@/config/navigation';
import { useT } from '@/i18n/useT';
import { useUiStore } from '@/stores/uiStore';
import { Logo } from '@/ui/Logo';

export function AppSidebar() {
  const t = useT();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);
  const label = collapsed ? t('header.expand') : t('header.collapse');
  const ToggleIcon = collapsed ? ChevronsRight : ChevronsLeft;

  return (
    <aside
      className={`hidden shrink-0 flex-col border-e border-line bg-panel transition-[width] duration-200 lg:flex ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      <div className={`flex h-14 shrink-0 items-center border-b border-line ${collapsed ? 'justify-center' : 'px-4'}`}>
        <Logo showText={!collapsed} />
      </div>

      <nav aria-label={t('app.name')} className="min-h-0 flex-1 overflow-y-auto py-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="mb-3 px-2">
            {collapsed ? (
              <div className="mx-2 mb-2 border-t border-line" />
            ) : (
              <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-mute">{t(group.labelKey)}</p>
            )}
            <ul>
              {group.items.map((item) => {
                const Icon = item.icon;
                const text = t(item.labelKey);
                return (
                  <li key={item.id}>
                    <NavLink
                      to={item.path}
                      end={item.path === '/'}
                      title={collapsed ? text : undefined}
                      aria-label={collapsed ? text : undefined}
                      className={({ isActive }) =>
                        `flex min-h-[40px] items-center gap-3 rounded border-s-2 px-2.5 text-sm transition-colors ${
                          isActive
                            ? 'border-cyan bg-elevated text-ink'
                            : 'border-transparent text-mute hover:bg-surface hover:text-ink'
                        } ${collapsed ? 'justify-center' : ''}`
                      }
                    >
                      <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                      {!collapsed && <span className="truncate">{text}</span>}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <button
        type="button"
        onClick={toggle}
        title={label}
        aria-label={label}
        className="flex h-11 shrink-0 items-center justify-center border-t border-line text-mute hover:text-ink"
      >
        <ToggleIcon className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
      </button>
    </aside>
  );
}
