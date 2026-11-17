import { describe, expect, it } from 'vitest';
import { ar } from './ar';
import { en } from './en';

describe('i18n dictionaries', () => {
  it('English and Arabic define exactly the same keys', () => {
    expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort());
  });

  it('has no empty strings', () => {
    for (const [k, v] of Object.entries(en)) expect(v.trim(), `en ${k}`).not.toBe('');
    for (const [k, v] of Object.entries(ar)) expect(v.trim(), `ar ${k}`).not.toBe('');
  });

  it('keeps the same {placeholders} in both languages', () => {
    const find = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(find(ar[key]), key).toEqual(find(en[key]));
    }
  });
});
