import { demoShot } from "./demoShots";

/** Base URL of the Nexus API. Empty string = same origin (the runner serves
 * both the UI and the API in single-process mode). Dev users set
 * NEXT_PUBLIC_NEXUS_URL to point at the running runner. */
export const NEXUS_URL = process.env.NEXT_PUBLIC_NEXUS_URL ?? "";

/** Resolve a `shot` reference from the backend into a browser-loadable URL. */
export function shotUrl(shot: string | undefined): string | null {
  if (!shot) return null;
  if (shot.startsWith("demo/")) return demoShot(shot);
  if (
    shot.startsWith("data:") ||
    shot.startsWith("http://") ||
    shot.startsWith("https://") ||
    shot.startsWith("/")
  ) {
    return shot;
  }
  return `${NEXUS_URL}/shots/${shot}`;
}

/** Split a URL into displayable parts. Never throws; malformed input becomes
 * host = whole string. */
export function splitUrl(url: string | undefined | null): { host: string; path: string } {
  if (!url) return { host: "", path: "" };
  try {
    const parsed = new URL(url);
    return {
      host: parsed.host,
      path: `${parsed.pathname}${parsed.search}`,
    };
  } catch {
    return { host: url.replace(/^https?:\/\//, "").slice(0, 32), path: "" };
  }
}

export function hostOf(url: string | undefined | null): string {
  return splitUrl(url).host;
}

/** First path segment (or the raw path when it is short); used for row
 * snippets in the sites list. */
export function pathSnippet(url: string | undefined | null, max = 26): string {
  const { path } = splitUrl(url);
  if (!path || path === "/") return "";
  const cleaned = path.endsWith("/") && path.length > 1 ? path.slice(0, -1) : path;
  return cleaned.length > max ? `${cleaned.slice(0, max - 1)}…` : cleaned;
}

/** Deterministic little hash for color derivation (host -> hue). */
export function hashString(input: string): number {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Stable gradient pair from a host string: no remote favicons, ever. */
export function hostGradient(host: string): { from: string; to: string; hue: number } {
  const hue = hashString(host || "site") % 360;
  return {
    hue,
    from: `hsl(${hue} 72% 62%)`,
    to: `hsl(${(hue + 48) % 360} 68% 42%)`,
  };
}
