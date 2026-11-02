const INT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function fmtInt(n: number): string {
  return INT.format(Math.round(n));
}

export function fmtCompact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${Math.round(n / 1000)}k`;
  if (abs >= 1_000) return `${(n / 1000).toFixed(1)}k`;
  return INT.format(Math.round(n));
}

export function fmtBytes(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} MB`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)} kB`;
  return `${Math.round(n)} B`;
}

/** share in [0,1] -> "62.4%" */
export function fmtPct(share: number): string {
  return `${(share * 100).toFixed(1)}%`;
}
