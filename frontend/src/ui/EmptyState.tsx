import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  body?: string;
  icon?: LucideIcon;
  children?: ReactNode;
}

export function EmptyState({ title, body, icon: Icon, children }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-center">
      {Icon && <Icon className="h-8 w-8 text-mute" aria-hidden="true" />}
      <p className="text-sm font-semibold">{title}</p>
      {body && <p className="max-w-md text-xs leading-relaxed text-mute">{body}</p>}
      {children}
    </div>
  );
}
