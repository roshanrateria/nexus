"""Capture the demo replay into web/shots/ for self-review.

Serves web/out statically (building it first if missing), then opens
http://localhost:3000/?demo=1 at three desktop viewports and screenshots at
t = 8 s / 25 s / 45 s into the replay. An extra hybrid-mode capture checks
the green privacy shield.

Run from the repo root:  python web/scripts/shots.py [--no-serve]
Output:                  web/shots/<w>x<h>_t<seconds>.png  (gitignored)
"""

import subprocess
import sys
import time
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
OUT = WEB / "out"
SHOTS = WEB / "shots"

VIEWPORTS = [(1440, 900), (1920, 1080), (1280, 720)]
TIMES = [8, 25, 45]
PORT = 3000


def ensure_build() -> None:
    if (OUT / "index.html").exists():
        return
    print("building web/ (next build)...", flush=True)
    subprocess.run(["npm", "run", "build"], cwd=WEB, check=True)


def main() -> int:
    if "--no-serve" not in sys.argv:
        ensure_build()

    from playwright.sync_api import sync_playwright

    server = None
    if "--no-serve" not in sys.argv:
        print(f"serving {OUT.name} on :{PORT}...", flush=True)
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(PORT)],
            cwd=OUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.2)

    SHOTS.mkdir(exist_ok=True)
    failures: list[str] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                for width, height in VIEWPORTS:
                    for t in TIMES:
                        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                        page.goto(f"http://localhost:{PORT}/?demo=1", wait_until="domcontentloaded")
                        page.wait_for_timeout(t * 1000)
                        # Hide the caret tail glitch is not needed; raw truth
                        # is what we want to review.
                        name = f"{width}x{height}_t{t:02d}.png"
                        page.screenshot(path=str(SHOTS / name))
                        print(f"captured {name}", flush=True)
                        page.close()
                # Hybrid-shield check at 1440x900, mid-run.
                page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                page.goto(f"http://localhost:{PORT}/?demo=1&mode=hybrid", wait_until="domcontentloaded")
                page.wait_for_timeout(25 * 1000)
                page.screenshot(path=str(SHOTS / "1440x900_t25_hybrid.png"))
                print("captured 1440x900_t25_hybrid.png", flush=True)
                page.close()
                # Graph stage (hotkey 3) mid-run at 1440x900.
                page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                page.goto(f"http://localhost:{PORT}/?demo=1", wait_until="domcontentloaded")
                page.wait_for_timeout(25 * 1000)
                page.keyboard.press("3")
                page.wait_for_timeout(2500)  # let the force simulation settle
                page.screenshot(path=str(SHOTS / "1440x900_t27_graph.png"))
                print("captured 1440x900_t27_graph.png", flush=True)
                page.close()
            finally:
                browser.close()
    except Exception as error:  # noqa: BLE001 - report and fail loudly
        failures.append(str(error))
    finally:
        if server is not None:
            server.terminate()

    if failures:
        print("FAILURES:", *failures, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
