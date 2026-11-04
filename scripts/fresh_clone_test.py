"""Fresh-clone E2E: judges get a green path from `git clone` to goal_achieved.

Phases (each timed):
  1. clone   - git clone this repo into a temp dir
  2. venv    - python -m venv inside the clone
  3. deps    - pip install -r requirements.txt
  4. browser - python -m playwright install chromium
  5. env     - copy the real .env over (value never printed)
  6. serve   - start runner.py serve mode on DASHBOARD_PORT=8799 headless, wait /health
  7. ui      - GET / must be 200 and contain the built UI (the committed web/out)
  8. run     - POST /run "Find the latest stable Python release version on
               python.org." and wait for a terminal state
  9. assert  - outcome goal_achieved, >= 1 evidence, report written, ledger sane

Usage:  python scripts/fresh_clone_test.py [--port 8799] [--timeout 480]
Exit 0 iff every phase passed.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_check import Recorder, fetch, wait_for_health  # noqa: E402

GOAL = "Find the latest stable Python release version on python.org."
PHASES: list[tuple[str, float]] = []


def step(name: str) -> float:
    print(f"[fresh_clone:{name}]", flush=True)
    return time.monotonic()


def done(name: str, start: float) -> None:
    took = round(time.monotonic() - start, 1)
    PHASES.append((name, took))
    print(f"[fresh_clone:{name}] ok in {took}s", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh-clone test")
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--timeout", type=float, default=480.0)
    parser.add_argument("--max-cost", type=float, default=1.0)
    args = parser.parse_args()

    clone_dir: Path | None = None
    t_all = time.monotonic()
    process = None
    failed = False
    try:
        start = step("clone")
        clone_dir = Path(tempfile.gettempdir()) / f"lumen_fresh_{uuid.uuid4().hex[:8]}"
        run_cmd(["git", "clone", "--quiet", str(ROOT), str(clone_dir)])
        done("clone", start)

        start = step("venv")
        run_cmd([sys.executable, "-m", "venv", str(clone_dir / ".venv")])
        venv_python = clone_dir / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if not venv_python.is_file():
            sys.exit(f"[fresh_clone:venv] {venv_python} missing")
        done("venv", start)

        start = step("deps")
        run_cmd([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=clone_dir)
        done("deps", start)

        start = step("browser")
        run_cmd([str(venv_python), "-m", "playwright", "install", "chromium"], cwd=clone_dir)
        done("browser", start)

        start = step("env")
        if not (ROOT / ".env").is_file():
            sys.exit("[fresh_clone:env] .env missing in the repo (values are never printed)")
        shutil.copy2(ROOT / ".env", clone_dir / ".env")
        done("env", start)

        start = step("serve")
        cond_lines: list[str] = []
        process = spawn_runner(clone_dir, venv_python, args.port, cond_lines)
        try:
            if not wait_for_health(args.port, seconds=150):
                sys.exit(f"[fresh_clone:serve] runner never answered /health:\n" + "\n".join(cond_lines[-40:]))
            done("serve", start)

            start = step("ui")
            status_code, body = fetch("GET", args.port, "/", timeout=10)
            text = body if isinstance(body, str) else ""
            if status_code != 200:
                sys.exit(f"[fresh_clone:ui] GET / -> HTTP {status_code}")
            if "data-testid" not in text and "nexus" not in text.lower():
                sys.exit("[fresh_clone:ui] served page does not look like the built UI")
            done("ui", start)

            start = step("run")
            run_doc = run_goal(args)
            done("run", start)

            start = step("assert")
            failed = not assert_ok(run_doc, clone_dir)
            done("assert", start)
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                process.wait(timeout=10)
    finally:
        if clone_dir is not None and clone_dir.exists():
            shutil.rmtree(clone_dir, ignore_errors=True)

    print("\n[timings]")
    for name, secs in PHASES:
        print(f"  {name:8} {secs:>6}s")
    print(f"  {'total':8} {round(time.monotonic() - t_all, 1):>6}s")
    print(f"\n[fresh_clone] {'ALL PASS' if not failed else 'FAILED'}")
    sys.exit(1 if failed else 0)


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", shell=False, cwd=cwd)
    except subprocess.CalledProcessError as error:
        tail = (error.stdout or "")[-800:] + (error.stderr or "")[-800:]
        sys.exit(f"[fresh_clone] command failed ({error.returncode}): {' '.join(cmd[:6])}...\n{tail}")


def spawn_runner(clone_dir: Path, venv_python: Path, port: int, lines: list[str]) -> subprocess.Popen:
    env = {**subprocess.os.environ, "DASHBOARD_PORT": str(port), "BROWSER_HEADLESS": "true"}
    process = subprocess.Popen(
        [str(venv_python), "runner.py"],
        cwd=clone_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )

    def reader() -> None:
        try:
            for line in process.stdout:
                lines.append(line.rstrip("\n"))
        except Exception:
            pass

    threading.Thread(target=reader, daemon=True).start()
    return process


def run_goal(args) -> dict:
    """POST the goal and watch the run until a terminal state or the budget.

    The recorder's /events SSE thread plus the /state polling loop below
    together capture the terminal snapshot (the hub resets /state moments
    after the finished event, so polling alone can miss it).
    """
    status_code, body = fetch("POST", args.port, "/run", {"goal": GOAL})
    if status_code != 202 or not isinstance(body, dict) or not body.get("run_id"):
        sys.exit(f"[fresh_clone:run] POST /run -> HTTP {status_code} {body!r}")
    recorder = Recorder(args.port, body["run_id"], args.timeout, args.max_cost)
    threading.Thread(target=recorder.stream_forever, daemon=True).start()
    start = time.monotonic()
    cancelled_reason: str | None = None
    while time.monotonic() - start <= args.timeout:
        try:
            _s, state = fetch("GET", args.port, "/state", timeout=3)
        except OSError:
            state = {}
        recorder.remember_state(state, "state-poll")
        if recorder.terminal:
            break
        if recorder.last_cost > args.max_cost:
            cancelled_reason = f"cost_usd {recorder.last_cost:.4f} exceeds cap {args.max_cost}"
            break
        time.sleep(0.5)
    if cancelled_reason or not recorder.terminal:
        recorder._note(cancelled_reason or f"timeout of {args.timeout}s reached: cancelling")
        recorder.cancel("cost cap" if cancelled_reason else "timeout")
        time.sleep(3)
        try:
            _s, state = fetch("GET", args.port, "/state", timeout=3)
            recorder.remember_state(state, "after-cancel")
        except OSError:
            pass
    return recorder.result()


def assert_ok(run_doc: dict, clone_dir: Path) -> bool:
    terminal = run_doc.get("terminal") or {}
    outcome = terminal.get("status") or ""
    evidences = terminal.get("evidences") or []
    ledger = terminal.get("ledger") or {}
    roles = ledger.get("by_role") or {}
    images_out = ((roles.get("planner") or {}).get("images_out") or 0) + ((roles.get("reporter") or {}).get("images_out") or 0)
    # the runner writes reports relative to ITS own cwd: the clone, not this repo
    check_run_id = run_doc.get("run_id") or ""
    report = clone_dir / "reports" / f"report_{check_run_id}.md"
    cost = float(ledger.get("cost_usd") or 0)
    wall = float(terminal.get("wall_s") or 0)
    print(f"\n[fresh_clone:run] id={check_run_id} wall={wall:.0f}s cost=${cost:.4f} evidences={len(evidences)}")
    checks = {
        "outcome goal_achieved": outcome == "goal_achieved",
        ">= 1 evidence": len(evidences) >= 1,
        "report written by the clone": report.is_file(),
        "planner/reporter images_out == 0": images_out == 0,
        "cost-positive ledger": cost > 0,
        "wall under 480s": 0 < wall < 480,
    }
    ok = all(checks.values())
    for name, passed in checks.items():
        print(f"    {'PASS' if passed else 'FAIL'}  {name}")
    return ok


if __name__ == "__main__":
    main()
