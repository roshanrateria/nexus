/** Deterministic gradient "screenshots" for the demo replay. Pure functions,
 * no randomness: every load of /?demo=1 renders identical frames.
 * Frames are 1280x800 SVGs (explicit width/height, so the browser reports
 * naturalWidth/naturalHeight). */

export const DEMO_SHOTS = ["demo/1", "demo/2", "demo/3", "demo/4", "demo/5", "demo/6"] as const;

interface Palette {
  accent: string;
  accent2: string;
  hair: string;
}

const PALETTES: Record<string, Palette> = {
  "demo/1": { accent: "#6d8bff", accent2: "#9f7bff", hair: "#2a3450" },
  "demo/2": { accent: "#34d399", accent2: "#5eead4", hair: "#24403a" },
  "demo/3": { accent: "#f59e0b", accent2: "#fbbf24", hair: "#443624" },
  "demo/4": { accent: "#f472b6", accent2: "#c084fc", hair: "#43273d" },
  "demo/5": { accent: "#60a5fa", accent2: "#22d3ee", hair: "#1f3a55" },
  "demo/6": { accent: "#a3e635", accent2: "#34d399", hair: "#2c3d21" },
};

const W = 1280;
const H = 800;
const CHROME = 52;

const URL_FOR: Record<number, string> = {
  1: "https://www.flipkart.com/search?q=wireless+headphones",
  2: "https://www.flipkart.com/search?q=wireless+headphones&sort=popularity",
  3: "https://www.flipkart.com/leaf-bass/product-reviews",
  4: "https://www.flipkart.com/zebronics-thunder/product-reviews",
  5: "https://www.flipkart.com/zebronics-thunder/p/itmzebth02",
  6: "https://www.flipkart.com/treadmill-headphone/p/itmtread03",
};

function esc(s: string): string {
  return encodeURIComponent(s).replace(/([()'!*])/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

function svgUri(svg: string): string {
  return `data:image/svg+xml,${esc(svg.replace(/\s+/g, " "))}`;
}

function text(x: number, y: number, content: string, fill: string, size = 13, weight = 500): string {
  return `<text x="${x}" y="${y}" font-family="monospace" font-size="${size}" font-weight="${weight}" fill="${fill}">${content.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</text>`;
}

function bars(gx: number, gy: number, gw: number, widths: number[], fill: string): string {
  return widths
    .map((w, i) => `<rect x="${gx}" y="${gy + i * 22}" width="${w * gw}" height="9" rx="4.5" fill="${fill}"/>`)
    .join("");
}

const DEFAULT_PALETTE: Palette = { accent: "#6d8bff", accent2: "#9f7bff", hair: "#2a3450" };

function card(x: number, y: number, w: number, h: number, p: Palette = DEFAULT_PALETTE, fill = "#131a2c"): string {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="16" fill="${fill}" stroke="${p.hair}"/>`;
}

function chrome(n: number, p: Palette): string {
  return `
    <rect x="0" y="0" width="${W}" height="${H}" rx="20" fill="#0d1220"/>
    <rect x="0" y="0" width="${W}" height="${H}" rx="20" fill="url(#g)" opacity=".16"/>
    <rect x="0" y="0" width="${W}" height="${CHROME}" rx="20" fill="#10162a"/>
    <rect x="0" y="${CHROME - 1}" width="${W}" height="1" fill="${p.hair}"/>
    <circle cx="30" cy="26" r="6.5" fill="#fb7185"/>
    <circle cx="54" cy="26" r="6.5" fill="#fbbf24"/>
    <circle cx="78" cy="26" r="6.5" fill="#34d399"/>
    <rect x="300" y="12" width="680" height="29" rx="15" fill="#0a0f1e" stroke="${p.hair}"/>
    <circle cx="322" cy="26.5" r="4.5" fill="${p.accent}"/>
    <path d="M 318 26.5 a4.5 4.5 0 0 1 9 0 Z M 322 27 l 0 3.5" stroke="#0a0f1e" fill="none"/>
    ${text(336, 31, URL_FOR[n] ?? "", "#c9d3e6", 12.5)}
    <rect x="1148" y="12" width="112" height="29" rx="15" fill="${p.accent}" opacity=".22"/>
    ${text(1188, 31, "NEXUS", p.accent2, 12, 700)}`;
}

function body(n: number, p: Palette): string {
  if (n === 1) {
    return `${text(48, 106, "152,742 items found for 'wireless headphones'", "#e8edf7", 20, 650)}
      ${text(48, 138, "Relevance · Flipkart search", "#8d9ab8", 13)}
      ${Array.from({ length: 6 }, (_, i) => {
        const x = 48 + (i % 3) * 404;
        const y = 176 + Math.floor(i / 3) * 296;
        return `${card(x, y, 380, 264)}
          <rect x="${x + 20}" y="${y + 20}" width="340" height="150" rx="12" fill="${i % 2 ? p.accent : p.accent2}" opacity=".55"/>
          ${bars(x + 24, y + 196, 300, [0.78, 0.52, 0.62], "#6d7a97")}
          <rect x="${x + 22}" y="${y + 228}" width="92" height="22" rx="11" fill="${p.accent}" opacity=".25"/>`;
      }).join("")}`;
  }
  if (n === 2) {
    return `${text(48, 112, "Top results · Popularity", "#e8edf7", 20, 650)}
      <rect x="510" y="82" width="170" height="34" rx="17" fill="${p.accent}" opacity=".3"/>
      ${text(556, 105, "SORTED", p.accent2, 14, 700)}
      ${Array.from({ length: 5 }, (_, i) => {
        const y = 156 + i * 122;
        return `${card(48, y, 1184, 104)
          }<rect x="${72 + i * 8}" y="${y + 18}" width="90" height="68" rx="12" fill="${[p.accent, p.accent2, "#818cf8", "#fbbf24", "#f472b6"][i]}" opacity=".6"/>
          ${bars(200, y + 26, 360, [0.9 - i * 0.08, 0.6, 0.45], "#8d9ab8")}
          ${text(640, y + 48, ["Leaf Bass Bluetooth Headset (Black, On the Ear)", "ZEBRONICS Zeb-Thunder ENC Mic (Black)", "Applee P47 Type-C Earphones", "Treadmill SPORTS RUNNING HEADPHPONE", "Leaf Bass Bassheads 900 On Ear"][i], "#e8edf7", 15, 650)}
          ${text(640, y + 76, ["₹799 · 63% off", "₹999 · 47% off", "₹349 · 78% off", "₹361 · 71% off", "₹899 · 40% off"][i] + "    " + ["4.2★ 12,846", "4.1★ 84,187", "4.0★ 96,132", "3.8★ 36", "4.2★ 41,208"][i], i === 3 ? p.accent2 : "#9fb2d4", 13)}`;
      }).join("")}`;
  }
  if (n === 3 || n === 4) {
    const title =
      n === 3
        ? "Leaf Bass Headset · 12,846 Ratings & 5,142 Reviews"
        : "Zeb-Thunder · 84,187 Ratings & 9,402 Reviews";
    return `${text(48, 112, title, p.accent2, 18, 650)
      }${card(48, 146, 356, 176)}
      ${bars(80, 190, 220, [0.85, 0.62, 0.38, 0.16, 0.07], p.accent)}
      ${text(80, 172, "4.2 ★ average", "#e8edf7", 15, 700)}
      ${Array.from({ length: 4 }, (_, i) => {
        const y = 356 + i * 106;
        return `${card(48, y, 1184, 88)}
          <circle cx="98" cy="${y + 44}" r="20" fill="${i % 2 ? p.accent2 : p.accent}" opacity=".7"/>
          ${bars(140, y + 22, 300, [0.4, 0.86], "#5b6a8a")}
          ${bars(140, y + 62, 1060, [0.94, 0.88, 0.8], "#55648a")}`;
      }).join("")}`;
  }
  // n === 5 / n === 6 : product pages
  return `<rect x="48" y="146" width="560" height="440" rx="18" fill="${p.accent}" opacity=".28"/>
    <rect x="168" y="266" width="260" height="260" rx="16" fill="${p.accent2}" opacity=".5"/>
    ${card(676, 146, 556, 130)}
    ${text(708, 196, n === 5 ? "ZEBRONICS Zeb-Thunder" : "Treadmill HEADPHPONE", "#e8edf7", 18, 650)}
    ${text(708, 228, n === 5 ? "₹999 · 60 Hrs playback · ENC Mic" : "₹361 · 71% off · 8 Hrs backup", p.accent2, 14, 650)}
    ${bars(708, 244, 460, [0.9, 0.55], "#6d7a97")}
    ${card(676, 296, 556, 58)}
    ${card(676, 370, 556, 58)}
    ${card(676, 444, 556, 58)}
    ${card(676, 518, 556, 58)}
    ${bars(708, 318, 420, [0.75], "#3c4a6b")}
    ${bars(708, 392, 420, [0.62], "#3c4a6b")}
    ${bars(708, 466, 420, [0.48], "#3c4a6b")}
    ${bars(708, 540, 420, [0.7], "#3c4a6b")}
    <rect x="676" y="612" width="220" height="44" rx="22" fill="${p.accent}" opacity=".4"/>
    ${text(716, 641, n === 5 ? "60 HRS PLAYBACK" : "65% OFF", p.accent2, 13, 700)}`;
}

function svg(name: string): string {
  const p = PALETTES[name] ?? PALETTES["demo/1"];
  const n = Number(name.slice(5));
  const inner = chrome(n, p) + body(n, p);
  const out = `
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<defs>
  <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="${p.accent}"/>
    <stop offset="1" stop-color="${p.accent2}"/>
  </linearGradient>
</defs>
${inner}
</svg>`;
  return svgUri(out);
}

const cache = new Map<string, string>();

/** `demo/N` -> gradient screenshot data URI. */
export function demoShot(name: string): string | null {
  if (!name.startsWith("demo/")) return null;
  const hit = cache.get(name);
  if (hit) return hit;
  const generated = svg(name);
  cache.set(name, generated);
  return generated;
}
