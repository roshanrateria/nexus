const INT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function fmtInt(n: number): string {
  return INT.format(Math.round(n));
}

/** Elapsed seconds -> "4:32" (or "1:04:32" past an hour). */
export function fmtElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/** USD cost with two decimals; null/absent reads as "n/a". */
export function fmtCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || Number.isNaN(usd)) return "n/a";
  return `$${usd.toFixed(2)}`;
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
