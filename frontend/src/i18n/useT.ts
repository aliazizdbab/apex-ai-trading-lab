import { useCallback } from 'react';
import { useUiStore, type Lang } from '@/stores/uiStore';
import { ar } from './ar';
import { en, type TKey } from './en';

export type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

export function translate(lang: Lang, key: TKey, vars?: Record<string, string | number>): string {
  const dict: Record<string, string> = lang === 'ar' ? ar : en;
  let text = dict[key] ?? en[key];
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.split(`{${name}}`).join(String(value));
    }
  }
  return text;
}

export function useT(): Translate {
  const lang = useUiStore((s) => s.lang);
  return useCallback((key, vars) => translate(lang, key, vars), [lang]);
}
