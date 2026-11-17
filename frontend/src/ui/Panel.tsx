import type { ReactNode } from 'react';

interface Props {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, actions, children, className = '' }: Props) {
  return (
    <section className={`min-w-0 rounded-md border border-line bg-panel ${className}`}>
      {(title || actions) && (
        <header className="flex min-h-[44px] flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
