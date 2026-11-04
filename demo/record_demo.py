"""D3: one-command REAL-run demo recorder for the Nexus dashboard.

Drives a genuine run end to end with Playwright and records it: intro card,
composer typing, the live dashboard during an actual agent run (goal POSTed
by the UI itself), the report/evidence/graph finale, outro card — with a fake
cursor + captions injected by demo/overlay.js. NOTHING is scripted or faked:
every caption (planner calls, tokens, cost, mode) is read from live /state.

What it does
------------
1. Preflight: refuses without MODEL_API_KEY, reuses a healthy idle server on
   --url, or starts `python runner.py` (serve mode, BROWSER_HEADLESS=true,
   DASHBOARD_OPEN=false) and waits for /health. Reads the live mode.
2. Generates the cards (demo/cards.py) for the live mode, then per attempt:
   a 1920x1080 Chromium context (color_scheme=dark, record_video_dir=w）.
3. Records: intro card 3.2s -> dashboard -> real mouse + keyboard into the
   composer -> Start -> monitor /state every 0.5s; fires each caption at most
   once (plan / verbatim evidence / retry-escalation / mode-specific line /
   reporting), keeps a "Time-lapse" badge over idles, and on goal_achieved
   shows the REAL run numbers, scrolls the report, opens the evidence sheet,
   then graph + live tabs -> outro card 5s.
4. Abort rules: status error/cancelled/other outcome, cost > --max-cost,
   or timeout -> POST /cancel; the attempt is FAILED, the raw video is kept
   for debugging, and the next attempt retries (fresh server run state).
   A final video is NEVER produced from a failed run.
5. Console errors / pageerrors during the dashboard scenes fail the attempt.
6. On success: demo/out/raw/<name>.webm + demo/out/marks.json
   (captions, idle intervals, scene boundaries, final state snapshot).
   Rendering to MP4 is edit.py's job (D4).

Usage:
    python demo/record_demo.py                       # goal from demo/goal.txt
    python demo/record_demo.py --goal "..."          # or an inline goal
    python demo/record_demo.py --no-video            # marks only, no capture
Exit 0 iff an attempt reached goal_achieved and was recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

DEMO_DIR = Path(__file__).resolve().parent
ROOT = DEMO_DIR.parent
OUT_DIR = DEMO_DIR / "out"
RAW_DIR = OUT_DIR / "raw"
OVERLAY_JS = DEMO_DIR / "overlay.js"

sys.path.insert(0, str(DEMO_DIR))
from cards import DEFAULT_TAGLINE, write_cards  # noqa: E402

# Caption cadence, seconds.
CAPTION_MS = 3600
FINISH_CAPTION_MS = 4000
INTRO_S = 3.2
OUTRO_S = 5.0
IDLE_AFTER_S = 5.0          # signature unchanged for this long -> time-lapse
IDLE_PAD_FRONT = 1.5        # the interval really opens at idle_start + this
IDLE_PAD_BACK = 0.5         # ... and ends at the next change minus this

# Real-state captions, each used at most once per run and <= 90 characters.
CAP_PLAN = "Planner (text only) splits the goal into steps"
CAP_EVIDENCE = "Every quote is checked verbatim against the page"
CAP_RETRY = "Verifier flagged a problem, so the planner re-plans"
CAP_CLOUD = "Cloud-only mode: all roles run on Muse Spark 1.3"
CAP_HYBRID = "Executor runs on open weights; Spark only plans and reports"
CAP_REPORT = "Report cites evidence IDs"
CAP_WELCOME = "Give it a goal. It does the rest."


def log(msg: str) -> None:
    print(f"[demo] {msg}", flush=True)


def ui_status(state: dict) -> str:
    """The spec's status set (running|reporting|done|goal_achieved|error|
    cancelled): 'done' is only a wrapper around the real outcome."""
    status = str(state.get("status") or "")
    outcome = str(state.get("outcome") or "")
    if status == "done":
        return outcome or "done"
    return status or (outcome or "done")


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 6.0):
    """stdlib HTTP; returns (status_code, parsed-or-text)."""
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                try:
                    return response.status, json.loads(raw)
                except ValueError:
                    return response.status, raw
            return response.status, raw
    except urllib.error.HTTPError as error:
        try:
            payload = error.read().decode("utf-8", "replace")
            return error.code, json.loads(payload)
        except (ValueError, OSError):
            return error.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ConnectionError(f"{type(error).__name__}: {error}") from error


def get_state(url: str, timeout: float = 6.0) -> dict:
    _code, state = http_json("GET", f"{url}/state", timeout=timeout)
    return state if isinstance(state, dict) else {}


def read_api_key() -> str | None:
    """MODEL_API_KEY from `.env` (never printed) or the environment."""
    env_file = ROOT / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("MODEL_API_KEY="):
                    value = line[len("MODEL_API_KEY="):].strip().strip('"').strip("'")
                    if value:
                        return value
        except OSError:
            pass
    value = os.environ.get("MODEL_API_KEY", "").strip()
    return value or None


def health(url: str) -> dict | None:
    try:
        _code, body = http_json("GET", f"{url}/health", timeout=3)
        return body if isinstance(body, dict) and body.get("ok") else None
    except ConnectionError:
        return None


def wait_for_health(url: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if health(url):
            return True
        time.sleep(0.5)
    return False


def start_runner(url: str) -> subprocess.Popen:
    """runner.py serve mode as a subprocess, headless agent browser, no popup."""
    env = {
        **os.environ,
        "BROWSER_HEADLESS": "true",
        "DASHBOARD_OPEN": "false",
    }
    process = subprocess.Popen(
        [sys.executable, "runner.py"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    port = urlsplit(url).port or (443 if urlsplit(url).scheme == "https" else 80)
    if not wait_for_health(url, seconds=120):
        try:
            process.terminate()
        except OSError:
            pass
        raise RuntimeError(f"runner.py never answered /health on :{port}")
    return process


def cancel_run(url: str, reason: str) -> None:
    log(f"cancel: {reason}")
    try:
        http_json("POST", f"{url}/cancel", {}, timeout=8)
    except ConnectionError:
        pass


def trim(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


# --------------------------------------------------------------------------
# One recorded attempt
# --------------------------------------------------------------------------

class Attempt:
    def __init__(self, args: argparse.Namespace, attempt_no: int, intro: Path, outro: Path):
        self.args = args
        self.no = attempt_no
        self.intro = intro
        self.outro = outro
        self.marks: dict = {
            "t0": time.strftime("%Y-%m-%d %H:%M:%S"),
            "attempt": attempt_no,
            "goal": args.goal,
            "mode": args.mode,
            "scenes": {},
            "captions": [],
            "idle_intervals": [],
            "console_errors": [],
            "trigger_log": [],
        }
        self.errors: list[str] = []
        self.captions_shown: set[str] = set()
        self.caption_busy_until = 0.0  # monotonic; no overlap, ever
        self.idle_open = None
        self.last_change = None        # monotonic time of the last signature change
        self.finished = False
        self.aborted: str | None = None

    def t(self) -> float:
        """Video time: seconds since the recording page was created."""
        return round(time.monotonic() - self.t0, 2)

    # ------------------------------------------------------------ helpers

    def show_caption(self, page, text: str, ms: int = CAPTION_MS) -> None:
        """Record a caption beat with real times (SRT sidecar). With
        --overlay-captions the pill is also rendered live in the video.
        Either way each caption fires at most once."""
        if text in self.captions_shown:
            return
        self.captions_shown.add(text)
        if not self.args.overlay_captions:
            shown = self.t()
            self.marks["captions"].append(
                {"text": text, "t_start": shown, "t_end": round(shown + ms / 1000.0, 2)}
            )
            log(f"caption(srt) @{shown:>6.1f}s: {text}")
            return
        while time.monotonic() < self.caption_busy_until:
            time.sleep(0.2)
        shown = self.t()
        page.evaluate("a => window.__demo.caption(a[0], a[1])", [text, ms])
        end = shown + ms / 1000.0
        self.caption_busy_until = time.monotonic() + ms / 1000.0
        self.marks["captions"].append(
            {"text": text, "t_start": shown, "t_end": round(end, 2)}
        )
        log(f"caption @{shown:>6.1f}s: {text}")

    def signature(self, state: dict) -> tuple:
        ledger = state.get("ledger") or {}
        current = state.get("current") or {}
        return (
            len(state.get("history") or []),
            len(state.get("evidences") or []),
            len(state.get("log") or []),
            int(ledger.get("planner_calls") or 0),
            ui_status(state),
            current.get("shot") or "",
        )

    def note_trigger(self, text: str) -> None:
        log(f"trigger @{self.t():.1f}s: {text}")
        self.marks["trigger_log"].append({"t": self.t(), "event": text})

    def move_to(self, page, locator, steps: int = 35) -> tuple[float, float]:
        box = locator.bounding_box()
        if not box:
            raise RuntimeError(f"no bounding box (locator not rendered?)")
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        page.mouse.move(x, y, steps=steps)
        return x, y

    # -------------------------------------------------------------- scene

    def run(self, browser) -> tuple[bool, str]:
        args = self.args
        url = args.url
        overlay = OVERLAY_JS.read_text(encoding="utf-8")

        kwargs = {
            "viewport": {"width": 1920, "height": 1080},
            "device_scale_factor": 1,
            "color_scheme": "dark",
        }
        if not args.no_video:
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            kwargs["record_video_dir"] = str(RAW_DIR)
            kwargs["record_video_size"] = {"width": 1920, "height": 1080}
        context = browser.new_context(**kwargs)
        context.add_init_script(overlay)
        self.t0 = time.monotonic()  # video starts when the page is created
        page = context.new_page()
        page.on("console", lambda m: self.errors.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.errors.append(str(e)[:200]))
        self.marks["scenes"]["recording_start"] = 0.0
        video = page.video if not args.no_video else None

        try:
            # -- intro card ------------------------------------------------
            page.goto(self.intro.as_uri())
            time.sleep(INTRO_S)
            self.marks["scenes"]["intro"] = [0.0, self.t()]

            # -- dashboard -------------------------------------------------
            page.goto(f"{url}/", wait_until="domcontentloaded")
            page.wait_for_selector('[data-testid="composer-input"]', timeout=30000)
            page.wait_for_timeout(600)
            self.marks["scenes"]["dashboard"] = [self.t(), None]
            self.show_caption(page, CAP_WELCOME)

            # Leftover run state (a previous failed attempt keeps its final
            # state pinned on the dashboard): open the "New run" sheet.
            composer = page.get_by_test_id("composer-input")
            if composer.count() == 0 or not composer.first.is_visible():
                self.note_trigger("stale state -> clicking the New run button")
                page.get_by_role("button", name="New run").first.click()
                page.wait_for_selector('[data-testid="composer-input"]', timeout=15000)
                page.wait_for_timeout(400)

            # -- real typing ------------------------------------------------
            x, y = self.move_to(page, page.get_by_test_id("composer-input"), steps=35)
            page.mouse.click(x, y)
            page.keyboard.type(args.goal, delay=28)
            start_button = page.get_by_test_id("composer-start")
            for _ in range(60):  # hydration / controlled-input settle
                if start_button.is_enabled():
                    break
                page.wait_for_timeout(500)
            else:
                return False, "composer-start never became enabled"
            self.marks["scenes"]["start_click_armed"] = self.t()
            _sx, _sy = self.move_to(page, start_button, steps=25)
            if args.no_video:
                # Rehearsal mode: type but never start a real run.
                self.marks["scenes"]["note"] = "no-video rehearsal: typed, not started"
                return True, "no-video rehearsal (typed, not started)"
            self.marks["scenes"]["start_click"] = self.t()
            page.mouse.click(_sx, _sy)

            # Stale-attempt retry ran inside a dialog sheet: close it now.
            if page.locator("[role='dialog']").count() > 0:
                page.wait_for_timeout(1200)
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

            # -- monitor the run -------------------------------------------
            self.marks["scenes"]["run_started"] = self.t()
            deadline = time.monotonic() + args.timeout
            prev_sig: tuple | None = None
            while True:
                now = time.monotonic()
                if now > deadline:
                    cancel_run(url, f"timeout of {args.timeout}s reached")
                    return False, f"timeout ({args.timeout}s)"
                try:
                    state = get_state(url)
                except ConnectionError as error:
                    self.note_trigger(f"/state unreachable: {error}")
                    time.sleep(0.5)
                    continue
                if not isinstance(state, dict):
                    time.sleep(0.5)
                    continue

                ledger = state.get("ledger") or {}
                cost = float(ledger.get("cost_usd") or 0.0)
                status = ui_status(state)
                sig = self.signature(state)

                # --- abort rules first -----------------------------------
                if status == "error":
                    return False, f"run error: {trim(str(state.get('outcome') or state.get('log', [{}])[-1].get('text', '')), 70)}"
                if status in ("cancelled", "budget_exhausted", "goal_unreachable"):
                    return False, f"run finished: {status}"
                if cost > args.max_cost:
                    cancel_run(url, f"cost ${cost:.4f} > cap ${args.max_cost:.2f}")
                    time.sleep(2.0)
                    return False, f"cost cap ${args.max_cost:.2f} exceeded"

                # --- signature change bookkeeping -------------------------
                if sig != prev_sig:
                    if prev_sig is not None and self.idle_open is not None:
                        closing = round(self.t() - IDLE_PAD_BACK, 2)
                        started = self.marks["idle_intervals"][-1]["start"]
                        self.marks["idle_intervals"][-1]["end"] = round(max(closing, started + 0.1), 2)
                        self.idle_open = None
                        page.evaluate("() => window.__demo.badge(false, 'Time-lapse')")
                        self.note_trigger("state changed -> time-lapse off")
                    self.last_change = time.monotonic()
                    prev_sig = sig

                # --- caption triggers (each at most once) ------------------
                self.fire_triggers(page, state)

                # --- finish? ----------------------------------------------
                if status == "goal_achieved":
                    self.finished = True
                    self.marks["scenes"]["finished"] = self.t()
                    break

                # --- idle / time-lapse ------------------------------------
                busy_soon = time.monotonic() < self.caption_busy_until
                if (
                    self.idle_open is None
                    and self.last_change is not None
                    and time.monotonic() - self.last_change >= IDLE_AFTER_S
                    and not busy_soon
                ):
                    start = round(self.t() - (time.monotonic() - self.last_change) + IDLE_PAD_FRONT, 2)
                    self.idle_open = {"start": start}
                    self.marks["idle_intervals"].append(dict(self.idle_open))
                    page.evaluate("a => window.__demo.badge(true, a[0])", ["Time-lapse"])
                    self.note_trigger(f"idle >= {IDLE_AFTER_S:.0f}s -> time-lapse on")

                time.sleep(0.5)

            # -- the flag finale (real values only) -------------------------
            self.finale(page, url)

            # -- outro card --------------------------------------------------
            page.goto(self.outro.as_uri())
            outro_start = self.t()
            time.sleep(OUTRO_S)
            self.marks["scenes"]["outro"] = [outro_start, self.t()]

            if self.errors:
                return False, "console/page errors during the dashboard scenes"
            return True, "ok"
        finally:
            self.marks["scenes"]["recording_end"] = self.t()
            try:
                page.close()
                context.close()  # flushes the video to disk
            except Exception:
                pass
            if video is not None:
                try:
                    raw = video.path()
                except Exception as error:  # video missing -> nothing to keep
                    self.marks["video_error"] = f"{type(error).__name__}: {error}"
                    raw = None
                if raw:
                    name = f"dash_{time.strftime('%H%M%S')}_a{self.no}"
                    destination = RAW_DIR / f"{name}.webm"
                    shutil.copyfile(raw, destination)
                    self.marks["video"] = str(destination.relative_to(ROOT))
                    log(f"raw video: {destination}")

    # ------------------------------------------------------------- triggers

    def fire_triggers(self, page, state: dict) -> None:
        mode = self.args.mode
        kind_seen = {row.get("kind") for row in (state.get("log") or [])}
        escalated = any(
            "Escalated to planner" in str(row.get("text") or "")
            for row in (state.get("log") or [])
        )
        if state.get("plan") and "plan" not in self.captions_shown:
            self.show_caption(page, CAP_PLAN)
        if (state.get("evidences") or []) and "evidence" not in self.captions_shown:
            self.show_caption(page, CAP_EVIDENCE)
        if (kind_seen & {"retry"}) or escalated:
            self.show_caption(page, CAP_RETRY)
        if mode == "cloud" and (state.get("visited") or []):
            self.show_caption(page, CAP_CLOUD)
        if mode == "hybrid" and (state.get("visited") or []):
            self.show_caption(page, CAP_HYBRID)
        if ui_status(state) == "reporting" and "report" not in self.captions_shown:
            self.note_trigger("reporting -> pressing 2")
            page.keyboard.press("2")
            self.show_caption(page, CAP_REPORT)

    # -------------------------------------------------------------- finale

    def finale(self, page, url: str) -> None:
        """goal_achieved: real numbers card, slow report scroll, evidence
        sheet, graph + live tabs." (times are video-time marks too)"""
        state = get_state(url)
        ledger = state.get("ledger") or {}
        cloud = ledger.get("cloud") or {}
        open_side = ledger.get("open") or {}
        total_tokens = int(cloud.get("prompt_tokens") or 0) + int(cloud.get("completion_tokens") or 0)
        total_tokens += int(open_side.get("prompt_tokens") or 0) + int(open_side.get("completion_tokens") or 0)
        planner_calls = int(ledger.get("planner_calls") or 0)
        steps = len(state.get("history") or [])
        cost_usd = float(ledger.get("cost_usd") or 0.0)
        self.marks["final"] = {
            "goal": state.get("goal"),
            "run_id": state.get("run_id"),
            "status": ui_status(state),
            "mode": state.get("mode"),
            "planner_calls": planner_calls,
            "steps": steps,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 4),
            "evidences": len(state.get("evidences") or []),
            "sites": len(state.get("visited") or []),
            "report_chars": len(str(state.get("report") or "")),
            "ledger": ledger,
        }
        log(f"final ledger: {planner_calls} calls, {steps} steps, {total_tokens:,} tokens, ${cost_usd:.4f}")

        page.wait_for_timeout(1500)
        caption = (
            f"{planner_calls} planner calls for {steps} steps - "
            f"{total_tokens:,} tokens - ${cost_usd:.2f}"
        )
        self.show_caption(page, caption, FINISH_CAPTION_MS)

        # blur anything focused so the hotkeys work again
        try:
            page.evaluate("() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); }")
        except Exception as error:
            self.note_trigger(f"blur failed: {type(error).__name__}")

        # report tab + slow scroll
        try:
            page.keyboard.press("2")
            page.wait_for_timeout(600)
            report = page.get_by_test_id("report-body")
            box = report.bounding_box()
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 80, steps=12)
                for _ in range(6):
                    page.mouse.wheel(0, 360)
                    page.wait_for_timeout(420)
        except Exception as error:
            self.note_trigger(f"report scroll failed: {type(error).__name__}")
            self.errors.append(f"report scroll: {error}")

        # first evidence chip -> sheet -> hold -> Esc
        try:
            chips = page.get_by_test_id("evidence-chip")
            if chips.count() > 0:
                chip = chips.first
                chip.scroll_into_view_if_needed()
                self.move_to(page, chip, steps=25)
                self.marks["scenes"]["evidence_sheet"] = self.t()
                _cx, _cy = self.move_to(page, chip, steps=10)
                page.mouse.click(_cx, _cy)
                page.wait_for_timeout(3000)
                page.keyboard.press("Escape")
                page.wait_for_timeout(600)
        except Exception as error:
            self.note_trigger(f"evidence sheet failed: {type(error).__name__}")
            self.errors.append(f"evidence sheet: {error}")

        # graph, then back to live
        try:
            page.keyboard.press("3")
            self.marks["scenes"]["graph"] = self.t()
            page.wait_for_timeout(3000)
            page.keyboard.press("1")
            self.marks["scenes"]["live"] = self.t()
            page.wait_for_timeout(2000)
        except Exception as error:
            self.note_trigger(f"stage tabs failed: {type(error).__name__}")
            self.errors.append(f"stage tabs: {error}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def human_summary(attempt: Attempt) -> None:
    marks = attempt.marks
    final = marks.get("final") or {}
    log("=== marks summary ===")
    log(json.dumps({
        "video": marks.get("video"),
        "captions": len(marks["captions"]),
        "idle_intervals": len(marks["idle_intervals"]),
        "status": final.get("status"),
        "planner_calls": final.get("planner_calls"),
        "steps": final.get("steps"),
        "total_tokens": final.get("total_tokens"),
        "cost_usd": final.get("cost_usd"),
        "evidences": final.get("evidences"),
        "sites": final.get("sites"),
    }, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the REAL-run Nexus demo")
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--goal-file", default=str(DEMO_DIR / "goal.txt"))
    parser.add_argument("--goal", default=None, help="inline goal; overrides --goal-file")
    parser.add_argument("--repo", default="", help="repo URL for the outro card")
    parser.add_argument("--tagline", default=DEFAULT_TAGLINE, help="intro card tagline")
    parser.add_argument("--max-cost", type=float, default=1.5, help="abort above this billed cost, USD")
    parser.add_argument("--timeout", type=float, default=540, help="abort above this run wall time, s")
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--no-video", action="store_true", help="marks only, no capture")
    parser.add_argument(
        "--overlay-captions",
        action="store_true",
        help="render caption pills live inside the video (default: captions are only"
        " recorded as marks and shipped as the .srt built by demo/edit.py)",
    )
    args = parser.parse_args()

    # -- record command surface for reproducibility --------------------------
    if args.goal is None:
        goal_path = Path(args.goal_file)
        if not goal_path.is_file():
            sys.exit(f"[demo] goal file not found: {goal_path}")
        args.goal = " ".join(goal_path.read_text(encoding="utf-8-sig").split())
    if not args.goal.strip():
        sys.exit("[demo] empty goal")

    # -- preflight: secret, health, mode --------------------------------------
    if read_api_key() is None:
        sys.exit("[demo] refusing to start: MODEL_API_KEY is missing from .env")

    url = args.url
    process = None
    server = health(url)
    if server and server.get("busy"):
        sys.exit("[demo] /health says busy — a run is already active; stop it or wait, then retry.")
    if server:
        log(f"reusing the healthy server on {url}")
    else:
        log(f"starting runner.py (serve mode, headless agent browser) for {url}")
        process = start_runner(url)
        log(f"runner.py is up on {url} (pid {process.pid})")

    try:
        state = get_state(url)
        mode = str(state.get("mode") or "cloud")
        args.mode = mode
        log(f"live mode: {mode}")
        if state.get("status") not in ("starting", "done", ""):
            log("note: a previous run's state is on the dashboard; the recorder will start a fresh New-run dialog.")
        intro, outro = write_cards(mode, args.tagline, args.repo)

        # -- attempts -----------------------------------------------------
        for attempt_no in range(1, max(1, args.attempts) + 1):
            attempt = Attempt(args, attempt_no, intro, outro)
            log(f"=== attempt {attempt_no}/{args.attempts} ===")
            ok, reason = False, "crashed"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--hide-scrollbars"])
                try:
                    ok, reason = attempt.run(browser)
                except Exception as error:  # a scene crash must still keep the raw video + marks
                    reason = f"recorder crash: {type(error).__name__}: {str(error)[:120]}"
                finally:
                    browser.close()
            marks_path = OUT_DIR / (f"marks.json" if ok else f"marks_failed_a{attempt_no}.json")
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            marks_path.write_text(json.dumps(attempt.marks, indent=2, ensure_ascii=False), encoding="utf-8")
            log(f"marks: {marks_path}")
            if ok:
                human_summary(attempt)
                log("SUCCESS — raw video + marks ready for demo/edit.py.")
                return
            log(f"attempt {attempt_no} FAILED: {reason} (raw video kept for debugging)")
            # A fresh attempt needs fresh state: restart the server we own.
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                process = start_runner(url)
        log("all attempts failed — refusing to produce a final video from a failed run.")
        raise SystemExit(1)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
