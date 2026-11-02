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
