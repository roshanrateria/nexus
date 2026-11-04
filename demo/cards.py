"""D2: title + end cards for the demo recording.

Generates self-contained intro.html / outro.html into demo/out/cards/
(dark glass style matching the Nexus app, 400ms fade-in); the recorder
loads them with page.goto(file://...).

The intro line set depends on the LIVE mode read from /state at record
time: hybrid adds the "Open-weights executor on Baseten" line. The outro
bullets come from demo/outro.json (see README "Built during the
hackathon"); the repo line renders whatever --repo holds, and says the
repo is unpublished when it is empty.

Standalone:  python demo/cards.py [--mode cloud|hybrid] [--tagline ...] [--repo URL]

record_demo.py imports write_cards() instead.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
OUTRO_JSON = DEMO_DIR / "outro.json"
OUT_DIR = DEMO_DIR / "out" / "cards"

DEFAULT_TAGLINE = "A browser agent that shows its receipts."

GLASS = "; ".join(
    [
        "background: rgba(16, 20, 27, .8)",
        "border: 1px solid rgba(148, 163, 184, .25)",
        "box-shadow: 0 24px 60px rgba(0, 0, 0, .5), inset 0 1px 0 rgba(255,255,255,.06)",
        "backdrop-filter: blur(14px)",
    ]
)

GRADIENT = (
    "background: linear-gradient(100deg, #818cf8 10%, #22d3ee 90%)"
)

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  html, body {{ margin: 0; height: 100%; }}
  body {{
    background: #0e1116;
    background-image:
      radial-gradient(1200px 600px at 50% -10%, rgba(96, 165, 250, .12), transparent 70%),
      radial-gradient(900px 500px at 85% 110%, rgba(192, 132, 252, .10), transparent 70%);
    color: #e6eaf0;
    font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    display: grid; place-items: center;
    overflow: hidden;
    animation: fade-in .4s ease-out both;
  }}
  @keyframes fade-in {{ from {{ opacity: 0 }} to {{ opacity: 1 }} }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(12px) }} to {{ opacity: 1; transform: none }} }}
  @keyframes spin {{ to {{ transform: rotate(360deg) }} }}
  .card {{
    {glass};
    border-radius: 26px;
    padding: 44px 56px;
    width: min(880px, 84vw);
    text-align: center;
    animation: rise .4s ease-out .08s both;
  }}
  .logo {{ display: inline-grid; place-items: center; margin-bottom: 12px;
           animation: spin 7s linear infinite; }}
  .name {{
    font-size: 68px; line-height: 1.05; font-weight: 700; letter-spacing: -.02em;
    {gradient}; background-clip: text; -webkit-background-clip: text; color: transparent;
  }}
  .name.small {{ font-size: 44px; }}
  .tagline {{ margin-top: 12px; font-size: 22px; color: #aeb8c8; }}
  .sub {{
    margin-top: 24px; padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, .18);
    font-size: 14.5px; color: #8b95a5; line-height: 1.75;
  }}
  .chip {{
    display: inline-block; margin-top: 20px; padding: 7px 16px;
    border: 1px solid rgba(148, 163, 184, .3); border-radius: 999px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 14px; color: #60a5fa; background: rgba(11, 14, 19, .7);
  }}
  h2 {{
    margin: 26px 0 12px; font-size: 13.5px; font-weight: 600;
    letter-spacing: .09em; text-transform: uppercase; color: #8b95a5;
  }}
  ul {{ margin: 0 auto; padding: 0; list-style: none; max-width: 760px; text-align: left; }}
  li {{ margin: 8px 0; padding-left: 28px; position: relative;
        font-size: 15.5px; color: #aeb8c8; line-height: 1.55; }}
  li::before {{ content: "\\2713"; position: absolute; left: 0; color: #34d399; font-weight: 700; }}
  .verified {{ margin-top: 26px; color: #c084fc; font-weight: 600; font-size: 16.5px; }}
</style>
</head>
<body>
  <div class="card">{body}</div>
</body>
</html>
"""

LOGO = """<div class="logo">
  <svg width="72" height="72" viewBox="0 0 32 32" aria-hidden="true">
    <defs>
      <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#818cf8"/><stop offset="1" stop-color="#22d3ee"/>
      </linearGradient>
    </defs>
    <circle cx="16" cy="16" r="12.5" fill="none" stroke="url(#lg)" stroke-opacity=".45" stroke-width="1.5"/>
    <path d="M10 21.5 L16 9.5 L22 21.5 Z" fill="none" stroke="url(#lg)" stroke-width="1.9"
          stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="10" cy="21.5" r="2.5" fill="#818cf8"/>
    <circle cx="22" cy="21.5" r="2.5" fill="#22d3ee"/>
    <circle cx="16" cy="9.5" r="2.8" fill="url(#lg)"/>
  </svg>
</div>"""


def load_bullets(path: Path = OUTRO_JSON) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        bullets = data.get("bullets") or []
        if isinstance(bullets, list) and bullets:
            return [str(b) for b in bullets][:4]
    except (OSError, ValueError):
        pass
    return []


def intro_html(mode: str, tagline: str) -> str:
    """Intro (dwell 3.2s in the recording): name, tagline, run-mode lines."""
    mode = (mode or "cloud").strip().lower()
    sub = ["Built with Muse Spark 1.3 on Meta Model API"]
    if mode == "hybrid":
        sub.append("Open-weights executor on Baseten")
    body = (
        LOGO
        + '<div class="name">Nexus</div>'
        + f'<div class="tagline">{html.escape(tagline)}</div>'
        + '<div class="sub">' + "<br>".join(html.escape(s) for s in sub) + "</div>"
    )
    return SHELL.format(title="Nexus", body=body, glass=GLASS, gradient=GRADIENT)


def outro_html(repo: str, bullets: list[str]) -> str:
    """Outro (dwell 5s): repo URL, hackathon bullets, verbatim-verification line."""
    repo = (repo or "").strip()
    if repo:
        repo_block = f'<div><span class="chip">{html.escape(repo)}</span></div>'
    else:
        repo_block = '<div><span class="chip" style="color:#8b95a5">code: unpublished hackathon repo</span></div>'
    rows = "".join(f"<li>{html.escape(text)}</li>" for text in bullets)
    body = (
        LOGO.replace('<div class="logo">', '<div class="logo" style="animation:none">', 1)
        + '<div class="name small">Nexus</div>'
        + repo_block
        + "<h2>Built during the hackathon</h2>"
        + f"<ul>{rows}</ul>"
        + '<div class="verified">Every claim is verified verbatim against the page.</div>'
    )
    return SHELL.format(title="Nexus", body=body, glass=GLASS, gradient=GRADIENT)


def write_cards(mode: str, tagline: str, repo: str, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    """Write intro.html + outro.html; return their paths (intro, outro)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bullets = load_bullets()
    intro_path = out_dir / "intro.html"
    outro_path = out_dir / "outro.html"
    intro_path.write_text(intro_html(mode, tagline), encoding="utf-8")
    outro_path.write_text(outro_html(repo, bullets), encoding="utf-8")
    return intro_path, outro_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo intro/outro cards")
    parser.add_argument("--mode", default="cloud", choices=["cloud", "hybrid"])
    parser.add_argument("--tagline", default=DEFAULT_TAGLINE)
    parser.add_argument("--repo", default="")
    args = parser.parse_args()
    intro_path, outro_path = write_cards(args.mode, args.tagline, args.repo)
    print(f"[cards] intro: {intro_path}")
    print(f"[cards] outro: {outro_path}")


if __name__ == "__main__":
    main()
