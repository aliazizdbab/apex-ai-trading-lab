import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'dark' | 'light';
export type Lang = 'en' | 'ar';

interface UiState {
  theme: Theme;
  lang: Lang;
  sidebarCollapsed: boolean;
  copilotOpen: boolean;
  favorites: string[];
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setLang: (lang: Lang) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleCopilot: () => void;
  setCopilotOpen: (open: boolean) => void;
  toggleFavorite: (symbol: string) => void;
}

/**
 * UI preferences. Persisted in this browser's localStorage only.
 * Server-side persistence arrives with the backend (Phase 2).
 */
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: 'dark',
      lang: 'en',
      sidebarCollapsed: false,
      copilotOpen: false,
      favorites: ['BTC/USDT', 'ETH/USDT'],
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
      setLang: (lang) => set({ lang }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleCopilot: () => set((s) => ({ copilotOpen: !s.copilotOpen })),
      setCopilotOpen: (copilotOpen) => set({ copilotOpen }),
      toggleFavorite: (symbol) =>
        set((s) => ({
          favorites: s.favorites.includes(symbol)
            ? s.favorites.filter((f) => f !== symbol)
            : [...s.favorites, symbol],
        })),
    }),
    { name: 'apex-ui', version: 1 },
  ),
);

/** Applies theme, language and text direction to <html>. */
export function applyUiToDocument(s: { theme: Theme; lang: Lang }): void {
  const root = document.documentElement;
  root.dataset.theme = s.theme;
  root.lang = s.lang;
  root.dir = s.lang === 'ar' ? 'rtl' : 'ltr';
}
