import { Link } from 'react-router-dom';
import { useT } from '@/i18n/useT';
import { EmptyState } from '@/ui/EmptyState';
import { Panel } from '@/ui/Panel';

export function NotFoundPage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-3xl">
      <Panel>
        <EmptyState title={t('common.notFoundTitle')} body={t('common.notFoundBody')}>
          <Link to="/" className="mt-2 inline-flex min-h-[44px] items-center rounded border border-line bg-surface px-4 text-sm hover:bg-elevated">
            {t('common.backHome')}
          </Link>
        </EmptyState>
      </Panel>
    </div>
  );
}
