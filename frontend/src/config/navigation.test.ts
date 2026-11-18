import { describe, expect, it } from 'vitest';
import { en } from '@/i18n/en';
import { ALL_NAV_ITEMS, MOBILE_TABS, NAV_GROUPS } from './navigation';

describe('navigation config', () => {
  it('exposes the 26 modules of the approved navigation', () => {
    expect(ALL_NAV_ITEMS).toHaveLength(26);
  });

  it('has unique ids and unique absolute paths', () => {
    expect(new Set(ALL_NAV_ITEMS.map((i) => i.id)).size).toBe(ALL_NAV_ITEMS.length);
    expect(new Set(ALL_NAV_ITEMS.map((i) => i.path)).size).toBe(ALL_NAV_ITEMS.length);
    for (const i of ALL_NAV_ITEMS) expect(i.path.startsWith('/')).toBe(true);
  });

  it('only references translation keys that exist', () => {
    for (const g of NAV_GROUPS) {
      expect(g.labelKey in en).toBe(true);
      for (const i of g.items) expect(i.labelKey in en).toBe(true);
    }
    for (const t of MOBILE_TABS) expect(t.labelKey in en).toBe(true);
  });

  it('mobile tabs point to real routes', () => {
    const paths = new Set(ALL_NAV_ITEMS.map((i) => i.path));
    for (const t of MOBILE_TABS) expect(paths.has(t.path)).toBe(true);
  });

  it('assigns every module to a roadmap phase between 1 and 16', () => {
    for (const i of ALL_NAV_ITEMS) {
      expect(i.phase).toBeGreaterThanOrEqual(1);
      expect(i.phase).toBeLessThanOrEqual(16);
    }
  });
});
