import { Search } from 'lucide-react';
import { useCallback, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ALL_NAV_ITEMS } from '@/config/navigation';
import { useClickOutside } from '@/hooks/useClickOutside';
import { useT } from '@/i18n/useT';

interface Props {
  onNavigate?: () => void;
  className?: string;
}

/** Searches the application's modules and navigates to the selected one. */
export function GlobalSearch({ onNavigate, className = '' }: Props) {
  const t = useT();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, close);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return ALL_NAV_ITEMS.filter((i) => t(i.labelKey).toLowerCase().includes(q)).slice(0, 8);
  }, [query, t]);

  const go = (path: string) => {
    navigate(path);
    setQuery('');
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div ref={ref} className={`relative ${className}`}>
      <div className="relative">
        <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-mute" aria-hidden="true" />
        <input
          type="search"
          value={query}
          placeholder={t('header.search')}
          aria-label={t('header.search')}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false);
            if (e.key === 'Enter' && results[0]) go(results[0].path);
          }}
          className="h-11 w-full rounded-md border border-line bg-surface ps-9 pe-3 text-sm placeholder:text-mute sm:h-9"
        />
      </div>
      {open && query.trim() !== '' && (
        <ul className="absolute inset-x-0 top-full z-40 mt-1 max-h-72 overflow-y-auto rounded-md border border-line bg-elevated py-1 shadow-lg">
          {results.length === 0 && <li className="px-3 py-2 text-xs text-mute">{t('header.searchEmpty')}</li>}
          {results.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => go(item.path)}
                  className="flex min-h-[44px] w-full items-center gap-2 px-3 text-start text-sm hover:bg-surface sm:min-h-[36px]"
                >
                  <Icon className="h-4 w-4 text-mute" aria-hidden="true" />
                  {t(item.labelKey)}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
