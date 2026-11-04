"""Run one goal through runner.py and gate it with hard PASS criteria.

Starts runner.py in serve mode as a subprocess (env BROWSER_HEADLESS=true,
DASHBOARD_PORT=<port>) unless /health already answers, POSTs the goal, records
a timeline (plan appeared, every step finish, retries, escalations, evidence
count, status changes, ledger snapshots) while polling /state every 0.5 s and
streaming /events, cancels on the cost cap or the timeout, then writes
runs/<run_id>/check.json and prints a PASS/FAIL table.

PASS requires ALL of: status goal_achieved; reports/report_<id>.md exists;
>= 3 evidences, each with id and shot; every [E#] in the report exists in
evidences; ledger tokens > 0 and cost_usd > 0; planner and reporter
images_out == 0; wall < 360 s; cost < $1.00; no traceback in the console log.

All HTTP via http.client — no third-party dependency.

Usage:  python scripts/run_check.py --goal "..." [--repeat 2] [--timeout 480]
                                        [--max-cost 1.0] [--port 8765]
Exit 0 iff every recorded run passes.
"""

import argparse
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fetch(method: str, port: int, path: str, body: dict | None = None, timeout: float = 5.0):
    """One HTTP request against the local hub; returns (status, json-or-str)."""
    conn = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, payload, headers)
        response = conn.getresponse()
        raw = response.read()
        if response.getheader("Content-Type", "").startswith("application/json"):
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, raw.decode("utf-8", "replace")
        return response.status, raw.decode("utf-8", "replace")
    finally:
        conn.close()


def wait_for_health(port: int, seconds: float = 90.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status, body = fetch("GET", port, "/health", timeout=2)
            if status == 200 and isinstance(body, dict) and body.get("ok"):
                return True
        except OSError:
            time.sleep(0.5)
    return False


class Recorder:
    """Records the run timeline and keeps the terminal snapshot.

    The hub resets its state moments after the finished event, so the /events
    stream (which broadcasts every state before that reset) is the only
    reliable source for terminal evidences and ledger. /state polling supplies
    the cost value for the budget cancel and a fallback snapshot.
    """

    def __init__(self, port: int, run_id: str, timeout: float, max_cost: float):
        self.port = port
        self.run_id = run_id
        self.timeout = timeout
        self.max_cost = max_cost
        self.lock = threading.Lock()
        self.timeline: list[dict] = []
        self.ledger_snaps: list[dict] = []
        self.terminal: dict = {}
        self.last_cost = 0.0
        self.status: str = "starting"
        self.evidence_count = 0
        self._started = time.monotonic()
        self._history_len = 0
        self._plan_seen = False
        self._noted_errors: set[str] = set()
        self._note("run POSTed")

    def elapsed(self) -> float:
        return time.monotonic() - self._started

    def _note(self, event: str) -> None:
        with self.lock:
            if len(self.timeline) < 300:
                self.timeline.append({"t": round(self.elapsed(), 1), "event": event})

    def _ledger_snap(self, ledger, force: bool = False) -> None:
        if not isinstance(ledger, dict) or not (ledger.get("cloud") or ledger.get("open")):
            return
        cost = float(ledger.get("cost_usd") or 0)
        with self.lock:
            self.last_cost = cost
            prev = self.ledger_snaps[-1] if self.ledger_snaps else None
            if not force and prev is not None:
                if abs(prev["cost_usd"] - cost) < 0.0005 and self.elapsed() - prev["t"] < 5:
                    return
                if self.elapsed() - prev["t"] < 2:
                    return
            self.ledger_snaps.append({
                "t": round(self.elapsed(), 1),
                "cost_usd": cost,
                "prompt_tokens": int(ledger.get("cloud", {}).get("prompt_tokens") or
                                     ledger.get("open", {}).get("prompt_tokens") or 0),
                "completion_tokens": int(ledger.get("cloud", {}).get("completion_tokens") or
                                         ledger.get("open", {}).get("completion_tokens") or 0),
            })

    def remember_state(self, state, source: str) -> None:
        if not isinstance(state, dict):
            return
        e = round(self.elapsed(), 1)
        self._ledger_snap(state.get("ledger"))
        new_status = state.get("status")
        with self.lock:
            old_status = self.status
            if isinstance(new_status, str) and new_status != old_status:
                self.status = new_status
                self.timeline.append({"t": e, "event": f"status {old_status} -> {new_status}"})
        error = state.get("error")
        if error:
            key = str(error)[:100]
            if key not in self._noted_errors:
                self._noted_errors.add(key)
                self._note(f"run error: {key}")
        if isinstance(state.get("plan"), list) and state["plan"] and not self._plan_seen:
            self._plan_seen = True
            self._note(f"plan appeared: {len(state['plan'])} step(s)")
        history = state.get("history") or []
        if isinstance(history, list) and len(history) > self._history_len:
            for record in history[self._history_len:]:
                evidences = record.get("evidences") or []
                self._note(f"step finished: verdict={record.get('verdict')} evidences={len(evidences)}")
            self._history_len = len(history)
        evidences = state.get("evidences") or []
        count = len(evidences) if isinstance(evidences, list) else 0
        if count != self.evidence_count:
            self.evidence_count = count
            self._note(f"evidences count: {count}")
        if new_status == "done" and not self.terminal:
            snapshot = {
                "status": state.get("outcome") or "goal_achieved",
                "report_path": state.get("report_path") or "",
                "evidences": [dict(ev) for ev in evidences if isinstance(ev, dict)],
                "ledger": json.loads(json.dumps(state.get("ledger") or {})),
                "wall_s": e,
            }
            with self.lock:
                self.terminal = snapshot

    def poll_forever(self) -> None:
        """Poll /state every 0.5 s: status changes, budget + timeout cancels."""
        while time.monotonic() - self._started <= self.timeout:
            try:
                _s, state = fetch("GET", self.port, "/state", timeout=3)
            except OSError:
                if self.terminal:
                    return
                time.sleep(0.5)
                continue
            self.remember_state(state, "state-poll")
            if self.terminal:
                return
            cost = self.last_cost
            if cost > self.max_cost:
                self._note(f"cost_usd {cost:.4f} exceeds cap {self.max_cost}: cancelling")
                self.cancel("cost cap")
                return
            time.sleep(0.5)
        self._note(f"timeout of {self.timeout}s reached: cancelling")
        self.cancel("timeout")

    def stream_forever(self) -> None:
        """GET /events: the state push stream. Alert frames (retry, escalation,
        budget, error) arrive as extra payloads and are recorded as events."""
        try:
            conn = HTTPConnection("127.0.0.1", self.port, timeout=90)
            conn.request("GET", "/events")
            response = conn.getresponse()
            while True:
                line = response.fp.readline()
                if not line:
                    return
                if not line.startswith(b"data: "):
                    continue
                try:
                    payload = json.loads(line[len(b"data: "):])
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if isinstance(payload.get("status"), str):
                    self.remember_state(payload, "events")
                    if self.terminal:
                        return
                else:
                    kind = payload.get("type", "alert")
                    detail = ""
                    if kind == "retry":
                        detail = f"attempt {payload.get('attempt')}/{payload.get('max')}: {payload.get('error', '')[:120]}"
                    elif kind == "escalation":
                        detail = f"reason={payload.get('reason')}"
                    elif kind == "budget":
                        detail = str(payload.get("message", ""))[:200]
                    elif kind == "error":
                        detail = str(payload.get("message", ""))[:200]
                    self._note(f"{kind}: {detail}".rstrip())
        except Exception:
            return  # SSE is best-effort; /state polling remains the fallback

    def cancel(self, reason: str) -> None:
        self._note(f"cancel requested ({reason})")
        try:
            fetch("POST", self.port, "/cancel", {}, timeout=5)
        except OSError:
            pass

    def result(self) -> dict:
        with self.lock:
            return {
                "run_id": self.run_id,
                "timeline": list(self.timeline),
                "ledger_snapshots": list(self.ledger_snaps),
                "terminal": dict(self.terminal),
            }


def start_runner(port: int, console_lines: list[str]) -> subprocess.Popen:
    """runner.py as a subprocess; a daemon reader thread drains stdout/stderr
    into console_lines immediately (rich output would otherwise fill the pipe
    buffer and block the server mid-run)."""
    env = {**subprocess.os.environ, "BROWSER_HEADLESS": "true", "DASHBOARD_PORT": str(port)}
    process = subprocess.Popen(
        [sys.executable, "runner.py"],
        cwd=ROOT,
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
                console_lines.append(line.rstrip("\n"))
        except Exception:
            pass

    threading.Thread(target=reader, daemon=True).start()
    return process


def check_run(goal: str, terminal: dict, console_text: str) -> tuple[dict, list[str]]:
    """The nine PASS gates from the spec."""
    checks: dict[str, bool] = {}
    notes: list[str] = []
    checks["status == goal_achieved"] = (terminal.get("status") or "") == "goal_achieved"
    run_id = terminal.get("run_id") or ""
    report = ROOT / "reports" / f"report_{run_id}.md"
    checks["report file exists"] = report.is_file()
    if not report.is_file():
        notes.append(f"missing {report}")
    evidences = terminal.get("evidences") or []
    checks[">= 3 evidences"] = len(evidences) >= 3
    ids = {ev.get("id") for ev in evidences}
    checks["evidences carry id+shot"] = bool(evidences) and all(ev.get("id") and ev.get("shot") for ev in evidences)
    report_text = report.read_text(encoding="utf-8", errors="replace") if report.is_file() else ""
    cited = sorted({hit.upper() for hit in re.findall(r"\[(E\d+)\]", report_text)})
    checks["every [E#] in report exists"] = bool(cited) and all(c in ids for c in cited)
    if report_text and not cited:
        notes.append("report carries no [E#] references")
    ledger = terminal.get("ledger") or {}
    cloud = ledger.get("cloud") or {}
    open_side = ledger.get("open") or {}
    prompt_tokens = int(cloud.get("prompt_tokens") or open_side.get("prompt_tokens") or 0)
    completion_tokens = int(cloud.get("completion_tokens") or open_side.get("completion_tokens") or 0)
    cost = float(ledger.get("cost_usd") or 0)
    checks["ledger tokens > 0"] = prompt_tokens > 0 and completion_tokens > 0
    checks["cost_usd > 0"] = cost > 0
    roles = ledger.get("by_role") or {}

    def images_out(role: str) -> int:
        return int((roles.get(role) or {}).get("images_out") or 0)

    checks["planner+reporter images_out == 0"] = images_out("planner") == 0 and images_out("reporter") == 0
    wall = float(terminal.get("wall_s") or 0)
    checks["wall < 360s"] = 0 < wall < 360
    checks["cost < $1.00"] = cost < 1.0
    checks["no traceback in log"] = "Traceback (most recent call last)" not in console_text
    if not evidences:
        notes.append("no terminal evidences captured")
    return checks, notes


def print_table(checks: dict[str, bool], notes: list[str]) -> bool:
    passed = all(checks.values())
    print(f"  {'PASS' if passed else 'FAIL'}")
    for name, ok in checks.items():
        print(f"    {'PASS' if ok else 'FAIL'}  {name}")
    for note in notes:
        print(f"    note: {note}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one goal and gate the result")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--timeout", type=float, default=480.0)
    parser.add_argument("--max-cost", type=float, default=1.0)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    process = None
    console_lines: list[str] = []
    if wait_for_health(args.port, seconds=2):
        print(f"[run_check] reusing the runner already serving on :{args.port}")
    else:
        process = start_runner(args.port, console_lines)
        print(f"[run_check] starting runner.py serve mode on :{args.port}")
        if not wait_for_health(args.port, seconds=90):
            process.terminate()
            process.wait(timeout=10)
            tail = "\n".join(console_lines[-30:])
            sys.exit(f"[run_check] runner never answered /health on :{args.port}\n{tail}")
    print(f"[run_check] /health OK on :{args.port}")

    overall = True
    for attempt in range(1, args.repeat + 1):
        offset_before = len(console_lines)
        status, body = fetch("POST", args.port, "/run", {"goal": args.goal})
        if status != 202 or not isinstance(body, dict) or not body.get("run_id"):
            overall = False
            print(f"[run_check] POST /run failed: HTTP {status} {body!r} — stopping")
            break
        run_id = body["run_id"]
        recorder = Recorder(args.port, run_id, args.timeout, args.max_cost)
        streamer = threading.Thread(target=recorder.stream_forever, daemon=True)
        poller = threading.Thread(target=recorder.poll_forever, daemon=True)
        streamer.start()
        poller.start()
        poller.join()  # terminal, cost-cap cancel, or run timeout
        time.sleep(1.5)  # let the reader thread catch late subprocess output
        console_text = "\n".join(console_lines[offset_before:])
        terminal = recorder.result()
        out_dir = ROOT / "runs" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "check.json").write_text(
            json.dumps({"goal": args.goal, "timeout": args.timeout, "max_cost": args.max_cost,
                        **terminal}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        if console_text:
            (out_dir / "console.log").write_text(console_text, encoding="utf-8")
        snapshot = terminal.get("terminal") or {}
        snapshot["run_id"] = run_id
        wall = float(snapshot.get("wall_s") or 0)
        cost = float((snapshot.get("ledger") or {}).get("cost_usd") or 0)
        print(f"\nrun {attempt}/{args.repeat}  id={run_id}  wall={wall:.0f}s  cost=${cost:.4f}")
        if not snapshot:
            print("  FAIL  (no terminal snapshot: run errored or was cancelled)")
            checks, notes = {"status == goal_achieved": False, "no traceback in log":
                             "Traceback (most recent call last)" not in console_text}, []
            overall = overall and print_table(checks, notes)
        else:
            overall = overall and print_table(*check_run(args.goal, snapshot, console_text))

    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        process.wait(timeout=10)
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
