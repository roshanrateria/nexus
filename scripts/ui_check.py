"""Playwright E2E over the built UI served by runner.py.

Opens http://127.0.0.1:8765/ (starting runner.py serve mode if /health does
not answer yet), types a short goal into composer-input, starts the run and
watches it live. While the run streams, each assertion records the maximum
ever observed (frames can tear down mid-refresh); after the finish a second
sample pins FIX1 — the hub keeps the final state, so the dashboard must still
show it 5 s later:

  * at least one plan-step, evidence-card;
  * browser-frame showing a frame (an img with naturalWidth > 0);
  * a non-empty report-body while the report streamed;
  * a visible ledger + stat-cost;
  * report-body still populated and evidence-card count unchanged 5 s
    after the run finished;
  * zero console errors and zero pageerrors.

Screenshots land in runs/<run_id>/ui_{third,twothirds,end}.png so every
assertion can be inspected. 1920x1080 viewport.

Usage:  python scripts/ui_check.py [--goal "..."] [--timeout 480] [--port 8765]
Exit 0 iff everything passed.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_check import fetch, start_runner, wait_for_health  # noqa: E402

DEFAULT_GOAL = "Find the latest stable Python release version and its release date on python.org. Cite sources."
RUNNING = {"running", "reporting"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright E2E over the served UI")
    parser.add_argument("--goal", default=DEFAULT_GOAL)
    parser.add_argument("--timeout", type=float, default=480.0, help="seconds to wait for the run to finish")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    process = None
    console_lines: list[str] = []
    if wait_for_health(args.port, seconds=2):
        print(f"[ui_check] reusing the runner already serving on :{args.port}")
    else:
        process = start_runner(args.port, console_lines)
        print(f"[ui_check] starting runner.py serve mode on :{args.port}")
        if not wait_for_health(args.port, seconds=90):
            sys.exit(f"[ui_check] runner never answered /health on :{args.port}")

    errors: list[str] = []
    result: dict = {"ok": False, "screenshots": [], "run_id": ""}
    best = {"plan_steps": 0, "evidence_cards": 0, "frame_imgs": 0, "report_chars": 0}
    # post-finish persistence probe (FIX1): pre-seeded keys keep sample_dom's
    # max() calls from raising KeyError into the blanket except
    final = {"plan_steps": 0, "evidence_cards": 0, "report_chars": 0}
    marks = {"running": False, "report_seen": False, "finished": False}
    started = time.monotonic()
    shots_taken: set[str] = set()
    checks: dict[str, bool] = {}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.on("console", lambda m: errors.append(f"console.error: {m.text[:200]}") if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))

            page.goto(f"http://127.0.0.1:{args.port}/", wait_until="domcontentloaded")
            composer = page.get_by_test_id("composer-input")
            button = page.get_by_test_id("composer-start")
            # The static export hydrates asynchronously: React's controlled
            # textarea wipes DOM values set before hydration, so fill -> check
            # enabled -> click, until the button accepts the text.
            for _ in range(40):
                composer.fill(args.goal)
                if button.is_enabled():
                    # force=True: the Magnetic spring wrapper keeps moving the
                    # button under the pointer, so actionability's stability
                    # check never settles on it.
                    button.click(force=True)
                    break
                time.sleep(0.5)
            else:
                sys.exit("[ui_check] composer-start never became enabled (hydration never saw the goal)")
            print("[ui_check] run started via the composer")

            def sample_dom(target: dict | None = None) -> None:
                """Record the counts ever seen; the post-finish probe passes
                its own dict to pin what the dashboard still shows (FIX1)."""
                dest = target if target is not None else best
                try:
                    dest["plan_steps"] = max(dest["plan_steps"], page.get_by_test_id("plan-step").count())
                    dest["evidence_cards"] = max(dest["evidence_cards"], page.get_by_test_id("evidence-card").count())
                    container = page.get_by_test_id("browser-frame")
                    imgs = container.locator("img")
                    for i in range(imgs.count()):
                        try:
                            if imgs.nth(i).evaluate("img => img.naturalWidth") > 0:
                                dest["frame_imgs"] = dest.get("frame_imgs", 0) + 1
                                break
                        except Exception:
                            pass
                    body = page.get_by_test_id("report-body")
                    if body.count():
                        dest["report_chars"] = max(dest["report_chars"], len(body.inner_text()))
                        if dest is best:
                            marks["report_seen"] = True
                except Exception:
                    pass  # a torn-down DOM during refresh is fine; keep polling

            def shots(run_id: str) -> None:
                """The 1/3 and 2/3 shots ride milestones (first plan-step, first
                report chunk) so every run duration yields all three; time
                fallbacks cover milestone-less runs."""
                if "third" not in shots_taken and (best["plan_steps"] >= 1 or time.monotonic() - started >= 90):
                    shots_taken.add("third")
                    _take(run_id, "third")
                if "twothirds" not in shots_taken and (marks["report_seen"] or time.monotonic() - started >= 180):
                    shots_taken.add("twothirds")
                    _take(run_id, "twothirds")

            def _take(run_id: str, name: str) -> None:
                target = ROOT / "runs" / run_id
                target.mkdir(parents=True, exist_ok=True)
                path = target / f"ui_{name}.png"
                page.screenshot(path=str(path))
                result["screenshots"].append(str(path.relative_to(ROOT)))
                print(f"[ui_check] screenshot: {path}")

            deadline = time.monotonic() + args.timeout
            run_id = ""
            last_dom = 0.0
            while True:
                elapsed = time.monotonic() - started
                if elapsed > args.timeout:
                    print(f"[ui_check] giving up after the {args.timeout}s budget")
                    break
                try:
                    _s, health = fetch("GET", args.port, "/health", timeout=2)
                except OSError:
                    health = {}
                try:
                    _s, state = fetch("GET", args.port, "/state", timeout=2)
                except OSError:
                    state = {}
                if isinstance(state, dict):
                    run_id = run_id or state.get("run_id", "")
                    if state.get("status") in RUNNING:
                        marks["running"] = True
                    if state.get("report"):
                        marks["report_seen"] = True
                    # /state mirrors the hub every 0.5 s; DOM follows suit
                    if time.monotonic() - last_dom >= 2.0:
                        last_dom = time.monotonic()
                        sample_dom()
                busy = None
                if isinstance(health, dict):
                    busy = bool(health.get("busy"))
                terminal = isinstance(state, dict) and state.get("status") in ("done", "error")
                if busy is False and terminal and marks["running"]:
                    # FIX1 keeps the hub state after the finish, so the
                    # terminal /state itself says the run is over; one more
                    # DOM sweep, then persistence is pinned below.
                    sample_dom()
                    marks["finished"] = True
                    break
                if run_id:
                    shots(run_id)
                time.sleep(0.5)
            result["run_id"] = run_id
            shots(run_id)
            target = ROOT / "runs" / run_id
            target.mkdir(parents=True, exist_ok=True)
            end_path = target / "ui_end.png"
            page.screenshot(path=str(end_path))
            result["screenshots"].append(str(end_path.relative_to(ROOT)))
            ledger_visible = page.get_by_test_id("ledger").is_visible()
            stat_cost_visible = page.get_by_test_id("stat-cost").is_visible()
            # FIX1 gate: 5 s after the finish the dashboard must still show
            # the final state (report text + evidence cards stay rendered).
            time.sleep(5)
            sample_dom(final)
            browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
            process.wait(timeout=10)
        # runner console for diagnosis (also records the tail on health fail)
        log = ROOT / "runs" / (result["run_id"] or "ui_only") / "console.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("\n".join(console_lines[-400:]), encoding="utf-8")

    checks = {
        "run started (running seen)": marks["running"],
        "run finished (terminal state seen)": marks["finished"],
        ">= 1 plan-step": best["plan_steps"] >= 1,
        ">= 1 evidence-card": best["evidence_cards"] >= 1,
        "browser-frame image loaded": best["frame_imgs"] >= 1,
        "report-body non-empty": best["report_chars"] > 0,
        "final state persists: report-body still populated 5s after finish": final.get("report_chars", 0) > 0,
        "final state persists: evidence-card count unchanged 5s after finish":
            final.get("evidence_cards", 0) == best["evidence_cards"] and best["evidence_cards"] >= 1,
        "ledger visible": ledger_visible,
        "stat-cost visible": stat_cost_visible,
        "no console errors / pageerrors": not errors,
    }
    result.update({k: v for k, v in best.items()})
    result["final_sample"] = dict(final)
    result["marks"] = dict(marks)
    result["errors"] = errors[:10]
    ok = all(checks.values())
    result["ok"] = ok
    out_dir = ROOT / "runs" / (result["run_id"] or "ui_only")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ui_check.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[ui_check] {'PASS' if ok else 'FAIL'}  (plan={best['plan_steps']}, evidence={best['evidence_cards']}, "
          f"frame_img={best['frame_imgs']}, report_chars={best['report_chars']}, "
          f"after_5s={final.get('evidence_cards')}/{final.get('report_chars', 0)}ch, wall={time.monotonic() - started:.0f}s)")
    for name, passed in checks.items():
        print(f"    {'PASS' if passed else 'FAIL'}  {name}")
    for error in errors[:10]:
        print(f"    error: {error}")
    for shot in result["screenshots"]:
        print(f"    screenshot: {shot}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
