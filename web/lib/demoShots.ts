/** Deterministic gradient "screenshots" for the demo replay. Pure functions,
 * no randomness: every load of /?demo=1 renders identical frames. */

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

function esc(s: string): string {
  return encodeURIComponent(s).replace(/([()'!*])/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

function svgUri(svg: string): string {
  return `data:image/svg+xml,${esc(svg.replace(/\s+/g, " "))}`;
}

function text(x: number, y: number, content: string, fill: string, size = 11, weight = 500): string {
  return `<text x="${x}" y="${y}" font-family="monospace" font-size="${size}" font-weight="${weight}" fill="${fill}">${content.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</text>`;
}

function bars(gx: number, gy: number, gw: number, widths: number[], fill: string): string {
  return widths
    .map((w, i) => `<rect x="${gx}" y="${gy + i * 16}" width="${w * gw}" height="7" rx="3.5" fill="${fill}"/>`)
    .join("");
}

function svg(name: string): string {
  const p = PALETTES[name] ?? PALETTES["demo/1"];
  const n = Number(name.slice(5));
  const chrome = `
    <rect width="960" height="600" rx="22" fill="#0d1220"/>
    <rect x="0" y="0" width="960" height="600" rx="22" fill="url(#g)" opacity=".14"/>
    <rect x="24" y="18" rx="9" width="26" height="26" fill="${p.hair}"/>
    <rect x="58" y="20" rx="18" width="878" height="22" fill="#161c2e" stroke="${p.hair}"/>
    ${text(72, 35, ["https://www.flipkart.com/search?q=wireless+headphones", "https://www.flipkart.com/search?q=wireless+headphones&sort=popularity", "https://www.flipkart.com/leaf-bass/product-reviews/pid=itmlf01", "https://www.flipkart.com/zebronics-thunder/product-reviews/pid=itlzb02", "https://www.flipkart.com/zebronics-thunder/p/itlzb02", "https://www.flipkart.com/treadmill-headphone/p/itltr03"][n - 1], "#c9d3e6", 10.5)}
    <circle cx="60" cy="31" r="4" fill="${p.accent}"/>`;
  let body = "";
  if (n === 1) {
    body = `${text(40, 88, "152,742 items found for 'wireless headphones'", "#e8edf7", 15, 650)}`
      + Array.from({ length: 6 }, (_, i) => {
        const x = 40 + (i % 3) * 306;
        const y = 120 + Math.floor(i / 3) * 216;
        return `<rect x="${x}" y="${y}" width="280" height="196" rx="14" fill="#131a2c" stroke="${p.hair}"/>
          <rect x="${x + 14}" y="${y + 14}" width="252" height="104" rx="10" fill="${i % 2 ? p.accent : p.accent2}" opacity=".55"/>
          ${bars(x + 20, y + 140, 240, [0.78, 0.52, 0.62], "#6d7a97")}
          <rect x="${x + 16}" y="${y + 176}" width="66" height="18" rx="9" fill="${p.accent}" opacity=".28"/>`;
      }).join("");
  } else if (n === 2) {
    body = text(40, 92, "Top results · Popularity", "#e8edf7", 15, 650)
      + `<rect x="392" y="66" width="132" height="26" rx="13" fill="${p.accent}" opacity=".3"/>`
      + text(414, 84, "SORTED", p.accent2, 11, 700)
      + Array.from({ length: 4 }, (_, i) => {
        const y = 124 + i * 112;
        return `<rect x="40" y="${y}" width="880" height="94" rx="14" fill="#131a2c" stroke="${p.hair}"/>
          <rect x="${58 + i * 14}" y="${y + 14}" width="66" height="62" rx="10" fill="${[p.accent, p.accent2, "#818cf8", "#fbbf24"][i]}" opacity=".6"/>
          ${bars(150, y + 22, 300, [0.9 - i * 0.08, 0.6, 0.45], "#8d9ab8")}
          ${text(470, y + 46, ["Leaf Bass Bluetooth Headset", "ZEBRONICS Zeb-Thunder ENC", "Applee P47 Type-C Earphones", "Treadmill RUNNING HEADPHPONE"][i], "#e8edf7", 12, 650)}
          ${text(470, y + 68, ["\u20B9799 \u00B7 63% off", "\u20B9999 \u00B7 47% off", "\u20B9349 \u00B7 78% off", "\u20B9361 \u00B7 71% off"][i] + "   " + ["4.2\u2605 12,846", "4.1\u2605 84,187", "4.0\u2605 96,132", "3.8\u2605 36"][i], i === 3 ? p.accent2 : "#9fb2d4", 10.5)}`;
      }).join("");
  } else if (n === 3 || n === 4) {
    const title = n === 3 ? "Leaf Bass Headset \u00B7 12,846 Ratings & 5,142 Reviews" : "Zeb-Thunder \u00B7 84,187 Ratings & 9,402 Reviews";
    body = text(40, 92, title, p.accent2, 14, 650)
      + `<rect x="40" y="112" width="270" height="120" rx="14" fill="#131a2c" stroke="${p.hair}"/>`
      + bars(64, 140, 200, [0.85, 0.62, 0.38, 0.16, 0.07], p.accent)
      + Array.from({ length: 3 }, (_, i) => {
        const y = 250 + i * 112;
        return `<rect x="40" y="${y}" width="880" height="94" rx="14" fill="#131a2c" stroke="${p.hair}"/>
          <circle cx="80" cy="${y + 42}" r="16" fill="${i % 2 ? p.accent2 : p.accent}" opacity=".7"/>
          ${bars(110, y + 22, 260, [0.4, 0.86], "#5b6a8a")}
          ${bars(110, y + 56, 810, [0.94, 0.88, 0.8], "#55648a")}`;
      }).join("");
  } else {
    body = `<rect x="40" y="108" width="440" height="330" rx="16" fill="${p.accent}" opacity=".28"/>`
      + `<rect x="124" y="196" width="200" height="200" rx="14" fill="${p.accent2}" opacity=".5"/>`
      + text(500, 130, "ZEBRONICS Zeb-Thunder", "#e8edf7", 15, 650)
      + text(500, 156, "\u20B91,099 \u00B7 60 Hrs playback \u00B7 ENC Mic", p.accent2, 12, 650)
      + bars(500, 180, 400, [0.9, 0.75, 0.62, 0.5, 0.68, 0.3], "#6d7a97")
      + `<rect x="500" y="318" width="150" height="30" rx="15" fill="${p.accent}" opacity=".4"/>`
      + text(524, 339, "65% OFF", p.accent2, 11, 700)
      + bars(500, 380, 420, [0.55, 0.4], "#3c4a6b")
      + Array.from({ length: 3 }, (_, i) => `<rect x="500" y="${410 + i * 52}" width="420" height="40" rx="12" fill="#131a2c" stroke="${p.hair}"/>`).join("");
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 600"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${p.accent}"/><stop offset="1" stop-color="${p.accent2}"/></linearGradient></defs>${roots()}${chrome}${body}</svg>`;
  return svgUri(svg);
}

function roots(): string {
  return "";
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
