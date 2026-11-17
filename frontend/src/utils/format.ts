/** Financial values always use Latin digits so columns align in both LTR and RTL. */
export function fmtPrice(n: number): string {
  const maxDigits = n >= 1000 ? 2 : n >= 1 ? 3 : 6;
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: maxDigits });
}

export function fmtPct(n: number): string {
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}

export function fmtCompact(n: number): string {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(n);
}
