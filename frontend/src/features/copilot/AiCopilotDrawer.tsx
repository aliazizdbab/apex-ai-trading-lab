import { useEffect } from 'react';
import { useUiStore } from '@/stores/uiStore';
import { AiCopilotWorkspace } from './AiCopilotWorkspace';

export function AiCopilotDrawer() {
  const copilotOpen = useUiStore((s) => s.copilotOpen);
  const setCopilotOpen = useUiStore((s) => s.setCopilotOpen);

  useEffect(() => {
    if (!copilotOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setCopilotOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [copilotOpen, setCopilotOpen]);

  if (!copilotOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45 backdrop-blur-[1px]">
      <div className="flex h-full w-full max-w-[500px] border-s border-line bg-panel shadow-2xl">
        <div className="h-full w-full">
          <AiCopilotWorkspace mode="drawer" onClose={() => setCopilotOpen(false)} />
        </div>
      </div>
    </div>
  );
}
