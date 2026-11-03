"""Contract guard between the Python backend and the web/lib TypeScript types.

No browser, no LLM: it publishes a scripted event sequence through Hub so the
state ends in every documented shape, then parses web/lib/types.ts with a
regex to compare interfaces, and finally boots the real HTTP server on an
ephemeral port to pin down handler behavior.

Run from the repo root:  python scripts/contract_check.py
Exit is non-zero when any check fails.
"""

import json
import re
import sys
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import os

os.chdir(ROOT)

from runner import Hub, RunControl, Server, make_handler

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({detail})' if detail else ''}")
    if not ok:
        failures.append(name)


def interface_keys(source: str, name: str) -> set[str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.DOTALL)
    if match is None:
        sys.exit(f"web/lib/types.ts has no `export interface {name} {{...}}`")
    keys = set()
    for line in match.group(1).splitlines():
        hit = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\??\s*:", line)
        if hit:
            keys.add(hit.group(1))
    return keys


# A scripted goal run that touches every event type the graph can emit,
# ending with an error event so the error shape is pinned too.
EVENTS: list[dict] = [
    {"type": "run", "goal": "Contract check goal", "run_id": "c0ffee12"},
    {"type": "plan", "round": 1, "status": "continue", "thought": "Start with the page.",
     "final_assessment": "",
     "plan": [{"instruction": "Open https://example.com and confirm it loads.",
               "expected_outcome": "Example Domain heading is visible."}]},
    {"type": "observe", "iteration": 0, "url": "https://example.com/", "title": "Example Domain",
     "shot": "c0ffee12/1.jpg"},
    {"type": "action", "iteration": 0, "name": "navigate", "args": {"url": "https://example.com/"}},
    {"type": "action_result", "name": "navigate", "ok": True, "content": "Navigated to https://example.com/"},
    {"type": "executor_report", "report": "STATUS: SUCCESS\nCURRENT STATE: example.com loaded."},
    {"type": "retry", "role": "executor", "attempt": 1, "max": 6, "error": "TimeoutError: slow", "wait": 2.0},
    {"type": "budget", "message": "Planning budget check fired in CI."},
    {"type": "escalation", "reason": "replan"},
    {"type": "evidence_check", "ok": 2, "failed": 1},
    {"type": "verified",
     "instruction": "Open https://example.com and confirm it loads.",
     "expected_outcome": "Example Domain heading is visible.",
     "complete": True, "verdict": "done",
     "assessment": "Heading verbatim on the page.",
     "report": "STATUS: SUCCESS\nCURRENT STATE: example.com loaded.",
     "evidences": [
         {"id": "E1", "url": "https://example.com/", "original_text": "Example Domain",
          "summarized": "The page shows the documented heading.", "shot": "c0ffee12/1.jpg"},
         {"id": "E2", "url": "https://example.com/", "original_text": "More information...",
          "summarized": "The link line is present.", "shot": "c0ffee12/1.jpg"},
     ],
     "shot": "c0ffee12/1.jpg", "url": "https://example.com/"},
    {"type": "ledger", "data": {
        "cloud": {"calls": 1, "prompt_tokens": 10, "completion_tokens": 5, "bytes_out": 120, "images_out": 0},
        "open": {"calls": 2, "prompt_tokens": 20, "completion_tokens": 8, "bytes_out": 260, "images_out": 2},
        "by_role": {"planner": {"calls": 1, "prompt_tokens": 10, "completion_tokens": 5, "bytes_out": 120, "images_out": 0},
                    "executor": {"calls": 2, "prompt_tokens": 20, "completion_tokens": 8, "bytes_out": 260, "images_out": 2}},
        "planner_calls": 1, "open_token_share": 0.7}},
    {"type": "report_reset"},
    {"type": "report_chunk", "text": "# Report\n\nVerified with evidence."},
    {"type": "report_done", "path": "reports/report_c0ffee12.md"},
    {"type": "finished", "status": "goal_achieved", "path": "reports/report_c0ffee12.md"},
    {"type": "error", "message": "ValueError: simulated failure for the contract check"},
]
COVERED = {"run", "plan", "observe", "action", "action_result", "executor_report", "verified",
           "retry", "budget", "escalation", "evidence_check", "ledger", "report_reset",
           "report_chunk", "report_done", "finished", "error"}


def check_state_contract() -> None:
    source = (ROOT / "web" / "lib" / "types.ts").read_text(encoding="utf-8")
    ts_state = interface_keys(source, "NexusState")
    ts_history = interface_keys(source, "HistoryRecord")
    ts_evidence = interface_keys(source, "Evidence")
    check("interfaces parsed", len(ts_state) >= 10 and len(ts_history) >= 8 and len(ts_evidence) >= 3,
          f"state={sorted(ts_state)} history={sorted(ts_history)} evidence={sorted(ts_evidence)}")

    hub = Hub(300)
    published = [event["type"] for event in EVENTS]
    for event in EVENTS:
        hub.publish(event)
    check("every event type applied", COVERED <= set(published), f"missing={sorted(COVERED - set(published))}")

    check("hub mode is one of the documented values", hub.state.get("mode") in ("hybrid", "cloud"), str(hub.state.get("mode")))

    final_keys = set(hub.state)
    check("final state matches NexusState keys exactly", final_keys == ts_state,
          f"python-only={sorted(final_keys - ts_state)} ts-only={sorted(ts_state - final_keys)}")
    for record in hub.state["history"]:
        missing = set(record) - ts_history
        check("HistoryRecord keys exist in TS", not missing, f"missing={sorted(missing)}")
        for evidence in record["evidences"]:
            missing = set(evidence) - ts_evidence
            check("Evidence keys exist in TS", not missing, f"missing={sorted(missing)}")


def check_http_contract() -> None:
    hub = Hub(300)
    control = RunControl()
    server = Server(("127.0.0.1", 0), make_handler(hub, control))
    port = server.server_address[1]
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"127.0.0.1:{port}"
    try:
        status, _body, headers, _data = request("GET", base, "/health")
        check("GET /health -> 200", status == 200, str(status))
        check("CORS header present", headers.get("Access-Control-Allow-Origin") == "*")

        status, body, _h, _d = request("GET", base, "/state")
        ok = status == 200
        try:
            json.loads(body)
        except ValueError:
            ok = False
        check("GET /state -> valid JSON", ok)

        first = first_event_line(base)
        ok = False
        if first:
            try:
                json.loads(first)
                ok = True
            except ValueError:
                pass
        check("first /events message parses as JSON", ok)

        status, _b, _h, _d = request("GET", base, "/shots/../x")
        check("escaped shots path -> 404", status == 404, str(status))

        status, body, headers, _d = request("GET", base, "/shots/c0ffee12/1.jpg")
        check("valid shot -> 200 image/jpeg", status == 200 and headers.get("Content-Type") == "image/jpeg",
              f"{status} {headers.get('Content-Type')}")

        status, body, _h, _d = request("POST", base, "/run", json.dumps({"goal": "   "}).encode())
        check("POST /run empty goal -> 400", status == 400, f"{status} {body!r}")

        status, _b, headers, _d = request("OPTIONS", base, "/run")
        methods = (headers.get("Access-Control-Allow-Methods") or "").replace(" ", "").split(",")
        allow = (headers.get("Access-Control-Allow-Headers") or "").replace(" ", "").split(",")
        check("OPTIONS allows POST + Content-Type",
              status == 204 and "POST" in methods and "Content-Type" in allow,
              f"{status} methods={methods} headers={allow}")
    finally:
        server.shutdown()
        server.server_close()


def request(method: str, authority: str, path: str, body: bytes | None = None):
    conn = HTTPConnection(authority, timeout=5)
    try:
        conn.request(method, path, body, {"Content-Type": "application/json"} if body else {})
        response = conn.getresponse()
        return response.status, response.read(), dict(response.getheaders()), response
    finally:
        conn.close()


def first_event_line(authority: str) -> str:
    conn = HTTPConnection(authority, timeout=5)
    try:
        conn.request("GET", "/events")
        response = conn.getresponse()
        line = response.readline().decode("utf-8", "replace")
        return line.removeprefix("data: ").strip() if line.startswith("data: ") else ""
    except Exception:
        return ""
    finally:
        conn.close()


def main() -> None:
    # A real (minimal) JPEG so the shot route can be exercised end to end.
    shot = ROOT / "runs" / "c0ffee12" / "shots" / "1.jpg"
    shot.parent.mkdir(parents=True, exist_ok=True)
    if not shot.is_file():
        jpeg = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01]) + b"\x00" * 32
        shot.write_bytes(jpeg + b"\xFF\xD9")

    check_state_contract()
    check_http_contract()

    print(f"\n{'ALL OK' if not failures else str(len(failures)) + ' failure(s): ' + ', '.join(failures)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
