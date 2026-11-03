import argparse
import asyncio
import contextlib
import json
import mimetypes
import queue
import re
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from agent import RUNS_DIR, BrowserSession, build_graph, build_models, check_model_key, resolve_mode
from ledger import Ledger
from schemas import Settings

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentic Browser</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
<style>
:root{--bg:#0e1116;--panel:#161b22;--line:#262d38;--text:#e6eaf0;--dim:#8b95a5;--ok:#34d399;--bad:#f87171;--warn:#fbbf24;--run:#60a5fa;--accent:#c084fc}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:12px 20px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{font-size:15px;margin:0;font-weight:600}
#goal{flex:1;min-width:260px;color:var(--dim)}
.badge{padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#243042;color:var(--run);text-transform:uppercase;letter-spacing:.04em}
.badge.goal_achieved,.badge.done{background:#10372b;color:var(--ok)}
.badge.goal_unreachable,.badge.budget_exhausted{background:#3f1d1d;color:var(--bad)}
.badge.reporting{background:#2e2147;color:var(--accent)}
main{display:grid;grid-template-columns:minmax(260px,1fr) minmax(320px,1.3fr) minmax(320px,1.4fr);gap:14px;padding:14px;height:calc(100vh - 58px)}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;overflow:auto;min-height:0}
section h2{margin:0 0 8px;font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.col{display:flex;flex-direction:column;gap:14px;min-height:0}
.col>section{flex:1}
ol{list-style:none;margin:0;padding:0}
li{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid var(--line)}
li:last-child{border-bottom:0}
.icon{width:16px;flex:none;text-align:center}
li.done .icon{color:var(--ok)}li.failed .icon{color:var(--bad)}li.active .icon{color:var(--run)}li.active{color:var(--text)}li.pending{color:var(--dim)}
.dim{color:var(--dim)}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;word-break:break-all}
.label{color:var(--accent);font-size:12px;font-weight:600;margin-bottom:2px}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0e13;border:1px solid var(--line);border-radius:6px;padding:8px;margin:6px 0 0;font:12px/1.45 ui-monospace,Menlo,monospace}
#log{font-size:12.5px}
.row{display:flex;gap:8px;padding:2px 0}
.time{color:var(--dim);flex:none;font-family:ui-monospace,Menlo,monospace}
.row.retry{color:var(--warn)}.row.error,.row.failed{color:var(--bad)}.row.ok{color:var(--ok)}.row.plan{color:var(--accent)}.row.action{color:var(--run)}
details{border-bottom:1px solid var(--line);padding:6px 0}
summary{cursor:pointer}
#report{font-size:14px}#report table{border-collapse:collapse;margin:8px 0}#report th,#report td{border:1px solid var(--line);padding:4px 8px}#report a{color:var(--run)}#report h1,#report h2{border-bottom:1px solid var(--line);padding-bottom:4px}
@media(max-width:1000px){main{grid-template-columns:1fr;height:auto}}
</style>
</head>
<body>
<header><h1>Agentic Browser</h1><span id="status" class="badge">starting</span><span id="run" class="dim mono"></span><div id="goal"></div></header>
<main>
  <div class="col">
    <section><h2>Plan</h2><ol id="plan"></ol><div id="thought" class="dim" style="margin-top:8px"></div></section>
    <section><h2>Current step</h2><div id="current"></div></section>
  </div>
  <div class="col">
    <section style="flex:2"><h2>Activity</h2><div id="log"></div></section>
    <section><h2>Evidence (<span id="evcount">0</span>)</h2><div id="evidence"></div></section>
  </div>
  <section><h2>Report <span id="reportpath" class="mono"></span></h2><div id="report" class="dim">The report appears here live once the planner finishes.</div></section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
let renderedEvidence = -1;
let renderedReport = null;
function render(s) {
  $('goal').textContent = s.goal || 'Waiting for a goal';
  $('run').textContent = s.run_id ? 'run ' + s.run_id : '';
  const label = s.status === 'done' ? s.outcome : s.status;
  const status = $('status');
  status.textContent = label.replace(/_/g, ' ');
  status.className = 'badge ' + label;
  const plan = $('plan');
  plan.replaceChildren();
  s.history.forEach((r) => {
    const li = el('li', r.complete ? 'done' : 'failed');
    li.append(el('b', 'icon', r.complete ? '✓' : '✗'), el('span', '', r.instruction));
    plan.append(li);
  });
  s.plan.forEach((p, i) => {
    const active = s.status === 'running' && i === 0;
    const li = el('li', active ? 'active' : 'pending');
    li.append(el('b', 'icon', active ? '▶' : '○'), el('span', '', p.instruction));
    plan.append(li);
  });
  if (!s.history.length && !s.plan.length) plan.append(el('li', 'pending', 'No plan yet'));
  $('thought').textContent = s.thought ? 'Planner: ' + s.thought : '';
  const cur = $('current');
  const c = s.current || {};
  cur.replaceChildren();
  if (c.instruction) cur.append(el('div', 'label', 'Instruction'), el('div', '', c.instruction));
  if (c.iteration !== undefined) cur.append(el('div', 'dim', 'State #' + c.iteration + ' · ' + (c.title || '')), el('div', 'dim mono', c.url || ''));
  if (c.shot) cur.append(el('div', 'dim mono', 'shot: ' + c.shot));
  if (c.last_action) cur.append(el('div', 'mono', '▶ ' + c.last_action));
  if (c.report) cur.append(el('div', 'label', 'Executor report'), el('pre', '', c.report));
  if (!c.instruction) cur.append(el('div', 'dim', 'Idle'));
  const log = $('log');
  const stick = log.parentElement.scrollTop + log.parentElement.clientHeight >= log.parentElement.scrollHeight - 40;
  log.replaceChildren();
  s.log.forEach((l) => {
    const row = el('div', 'row ' + l.kind);
    row.append(el('span', 'time', l.t), el('span', '', l.text));
    log.append(row);
  });
  if (stick) log.parentElement.scrollTop = log.parentElement.scrollHeight;
  if (s.evidences.length !== renderedEvidence) {
    renderedEvidence = s.evidences.length;
    $('evcount').textContent = s.evidences.length;
    const ev = $('evidence');
    ev.replaceChildren();
    s.evidences.forEach((e) => {
      const d = el('details');
      d.append(el('summary', '', '[' + (e.id || e.url) + '] ' + e.summarized), el('div', 'dim mono', e.url), el('pre', '', e.original_text));
      ev.append(d);
    });
  }
  if (s.report !== renderedReport) {
    renderedReport = s.report;
    if (s.report) $('report').innerHTML = DOMPurify.sanitize(marked.parse(s.report));
  }
  $('reportpath').textContent = s.report_path || '';
}
const source = new EventSource('/events');
source.onmessage = (message) => render(JSON.parse(message.data));
</script>
</body>
</html>
"""


# Startup banner required by the Meta Model API privacy story: users must see
# which endpoints process screenshots in the active mode.
BANNERS = {
    "hybrid": "Mode: HYBRID | planner+reporter -> Meta Spark | executor+verifier -> Baseten",
    "cloud": "Mode: CLOUD-ONLY | all roles -> Meta Spark (screenshots are processed by Meta Model API)",
}


class Hub:
    def __init__(self, max_log: int, mode: str = "cloud"):
        self.max_log = max_log
        self.mode = mode
        self.lock = threading.Lock()
        self.subscribers: list[queue.Queue] = []
        self.state: dict = self._initial()

    def _initial(self) -> dict:
        return {
            "goal": "",
            "run_id": "",
            "status": "starting",
            "outcome": "",
            "mode": self.mode,
            "thought": "",
            "plan": [],
            "history": [],
            "evidences": [],
            "current": {},
            "log": [],
            "report": "",
            "report_path": "",
            "ledger": {},
            "visited": [],
        }

    def reset(self) -> None:
        """Restore the pre-run state for the next goal. Open SSE subscribers
        are kept so a connected UI stays live and just sees the blank state."""
        with self.lock:
            self.state = self._initial()
            self.broadcast()

    def note(self, kind: str, text: str) -> None:
        self.state["log"].append({"t": time.strftime("%H:%M:%S"), "kind": kind, "text": text})
        del self.state["log"][: -self.max_log]

    def seed(self, values: dict) -> None:
        with self.lock:
            history = values.get("history", [])
            self.state.update(
                goal=values["goal"],
                run_id=values["run_id"],
                status="running",
                plan=values.get("plan", []),
                history=history,
                evidences=[e for record in history for e in record["evidences"]],
            )
            self.note("plan", f"Resumed run {values['run_id']} with {len(history)} finished step(s)")
            self.broadcast()

    def subscribe(self) -> queue.Queue:
        channel: queue.Queue = queue.Queue()
        with self.lock:
            channel.put(json.dumps(self.state))
            self.subscribers.append(channel)
        return channel

    def unsubscribe(self, channel: queue.Queue) -> None:
        with self.lock:
            self.subscribers.remove(channel)

    def broadcast(self) -> None:
        payload = json.dumps(self.state)
        for channel in self.subscribers:
            channel.put(payload)

    def publish(self, event: dict) -> None:
        with self.lock:
            self.apply(event)
            self.broadcast()

    def _track_visit(self, s: dict, e: dict) -> None:
        """Sites visited for this run, deduped by URL: visiting again bumps
        `visits` and moves the entry to the front (newest first). Reset
        between runs comes for free via `_initial()`."""
        url = e.get("url") or ""
        if not url or url == "about:blank":
            return
        title = e.get("title") or ""
        now = time.strftime("%H:%M:%S")
        visited = s["visited"]
        for entry in visited:
            if entry["url"] == url:
                entry["visits"] += 1
                if title:
                    entry["title"] = title
                entry["last_t"] = now
                visited.insert(0, visited.pop(visited.index(entry)))
                break
        else:
            visited.insert(0, {
                "url": url,
                "host": urlsplit(url).netloc,
                "title": title,
                "visits": 1,
                "first_t": now,
                "last_t": now,
            })

    def apply(self, e: dict) -> None:
        s = self.state
        kind = e["type"]
        if kind == "run":
            s.update(goal=e["goal"], run_id=e["run_id"], status="running")
        elif kind == "plan":
            s.update(
                status="running" if e["status"] == "continue" else e["status"],
                thought=e["thought"],
                plan=e["plan"],
                current={"instruction": e["plan"][0]["instruction"]} if e["plan"] else {},
            )
            self.note("plan", f"Round {e['round']}: {e['status']}, {len(e['plan'])} step(s) planned. {e['thought']}")
        elif kind == "observe":
            s["current"].update(iteration=e["iteration"], url=e["url"], title=e["title"], shot=e.get("shot", ""))
            self._track_visit(s, e)
        elif kind == "action":
            s["current"]["last_action"] = f"{e['name']}({json.dumps(e['args'], ensure_ascii=False)})"
            self.note("action", s["current"]["last_action"])
        elif kind == "action_result":
            self.note("ok" if e["ok"] else "error", f"{e['name']}: {e['content']}")
        elif kind == "executor_report":
            s["current"]["report"] = e["report"]
            self.note("action", "Executor reported back")
        elif kind == "verified":
            # History records keep the exact documented shape (no event
            # metadata), matching what resume seeds from the checkpoint.
            record = {key: value for key, value in e.items() if key != "type"}
            s["history"].append(record)
            s["evidences"].extend(record["evidences"])
            verdict = {"done": "Step verified", "retry": "Step NOT complete, retrying locally", "replan": "Step NOT complete, escalating to planner"}[e["verdict"]]
            self.note("ok" if e["complete"] else "failed", f"{verdict}: {e['assessment']}")
        elif kind == "escalation":
            self.note("plan", f"Escalated to planner: {e['reason']}")
        elif kind == "evidence_check":
            rejected = e.get("rejected") or []
            debug_hint = f" e.g. {rejected[0]!r}" if rejected else ""
            self.note("ok" if e["failed"] == 0 else "failed", f"Evidence check: {e['ok']} verified, {e['failed']} rejected{debug_hint}")
        elif kind == "retry":
            self.note("retry", f"{e['role']} failed (attempt {e['attempt']}/{e['max']}): {e['error']}. Retrying in {e['wait']}s")
        elif kind == "budget":
            self.note("failed", e["message"])
        elif kind == "report_reset":
            s.update(report="", status="reporting")
        elif kind == "report_chunk":
            s["report"] += e["text"]
            s["status"] = "reporting"
        elif kind == "report_done":
            s["report_path"] = e["path"]
            self.note("ok", f"Report saved to {e['path']}")
        elif kind == "ledger":
            s.update(ledger=e["data"])
        elif kind == "error":
            s.update(status="error", outcome="error", current={})
            self.note("error", e["message"])
        elif kind == "finished" and e["status"] == "cancelled":
            s.update(status="done", outcome="cancelled", current={})
        elif kind == "finished":
            s.update(status="done", outcome=e["status"], current={})


class RunControl:
    """Hand-off between HTTP worker threads and the asyncio loop that runs goals.

    The queue carries `(goal, run_id)` pairs; goals cross threads via
    `loop.call_soon_threadsafe(queue.put_nowait, item)`. `busy` is a
    lock-guarded flag flipped only from the loop side, so HTTP threads can
    read it without racing the run loop.
    """

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.lock = threading.Lock()
        self._busy = False

    @property
    def busy(self) -> bool:
        with self.lock:
            return self._busy

    def set_busy(self, value: bool) -> None:
        with self.lock:
            self._busy = value

    def enqueue(self, goal: str, run_id: str) -> None:
        item = (goal, run_id)
        if self.loop is None:
            self.queue.put_nowait(item)  # no live loop yet (scripted checks)
        else:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, item)


SHOTS_URL_RE = re.compile(r"^shots/([a-f0-9]{8})/(\d+)\.jpg$")

# Next.js static export directory, served from the same process (below, see
# make_handler). Missing it just falls back to the legacy inline dashboard.
WEB_OUT = Path(__file__).resolve().parent / "web" / "out"

# Explicit map keeps content types stable regardless of the Windows registry,
# which mimetypes reads on this platform.
STATIC_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        return None


def make_handler(hub: Hub, control: RunControl):
    class Handler(BaseHTTPRequestHandler):
        legacy_hint_shown = False

        def log_message(self, *args) -> None:
            return None

        def _send(self, status: int, content_type: str, body: bytes, extra: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if not getattr(self, "_head", False):
                self.wfile.write(body)

        def do_GET(self) -> None:
            path = unquote(urlsplit(self.path).path).lstrip("/")
            if path in ("", "index.html"):
                self.static("index.html")
            elif path == "legacy":
                self.legacy()
            elif path == "events":
                self.stream()
            elif path == "state":
                with hub.lock:
                    body = json.dumps(hub.state).encode("utf-8")
                self._send(200, "application/json", body)
            elif path == "health":
                self._send(200, "application/json", json.dumps({"ok": True, "busy": control.busy}).encode("utf-8"))
            elif path.startswith("shots/"):
                match = SHOTS_URL_RE.match(path)
                if match:
                    self.shot(match)
                else:
                    self._send(404, "text/plain", b"not found")
            else:
                self.static(path)

        def do_HEAD(self) -> None:
            self._head = True
            try:
                self.do_GET()
            finally:
                self._head = False

        def do_OPTIONS(self) -> None:
            self._send(
                204,
                "text/plain",
                b"",
                extra={"Access-Control-Allow-Methods": "POST, GET, HEAD, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"},
            )

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path == "/run":
                self.run_goal()
            elif path == "/cancel":
                self.cancel_goal()
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

        def run_goal(self) -> None:
            """Queue a goal for the run loop. The busy flag is flipped on the
            loop side, so between the 202 and the actual start one more goal
            could slip into the queue: runs simply stay sequential."""
            try:
                length = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self._send(400, "application/json", b'{"error": "body must be JSON: {\\"goal\\": ...}"}')
                return
            goal = data.get("goal") if isinstance(data, dict) else None
            if not isinstance(goal, str) or not goal.strip():
                self._send(400, "application/json", b'{"error": "goal must be a non-empty string"}')
                return
            goal = goal.strip()
            if len(goal) > 2000:
                self._send(400, "application/json", b'{"error": "goal must be 2000 characters or fewer"}')
                return
            if control.busy:
                self._send(409, "application/json", b'{"error": "busy"}')
                return
            run_id = uuid.uuid4().hex[:8]
            control.enqueue(goal, run_id)
            self._send(202, "application/json", json.dumps({"run_id": run_id}).encode("utf-8"))

        def cancel_goal(self) -> None:
            task = control.task
            if not control.busy or task is None or task.done():
                self._send(409, "application/json", b'{"error": "idle"}')
                return
            control.loop.call_soon_threadsafe(task.cancel)
            self._send(200, "application/json", b'{"ok": true}')

        def legacy(self) -> None:
            if not Handler.legacy_hint_shown:
                print("Run: python scripts/build_ui.py")
                Handler.legacy_hint_shown = True
            self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML.encode("utf-8"))

        def static(self, rel: str) -> None:
            """Serve a file from web/out (Next.js export). Paths that escape
            the directory, or simply do not exist, get a 404."""
            if not (WEB_OUT / "index.html").is_file():
                self.legacy()
                return
            try:
                candidate = (WEB_OUT / rel).resolve()
                candidate.relative_to(WEB_OUT.resolve())
            except (OSError, ValueError):
                self._send(404, "text/plain", b"not found")
                return
            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.is_file():
                self._send(404, "text/plain", b"not found")
                return
            ctype = STATIC_TYPES.get(candidate.suffix.lower())
            if ctype is None:
                ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self._send(200, ctype, candidate.read_bytes())

        def shot(self, match) -> None:
            target = Path(RUNS_DIR) / match.group(1) / "shots" / f"{match.group(2)}.jpg"
            if not target.is_file():
                self._send(404, "text/plain", b"not found")
                return
            self._send(200, "image/jpeg", target.read_bytes())

        def stream(self) -> None:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            channel = hub.subscribe()
            try:
                while True:
                    self.wfile.write(f"data: {channel.get()}\n\n".encode("utf-8"))
                    self.wfile.flush()
            finally:
                hub.unsubscribe(channel)

    return Handler


class Dashboard:
    def __init__(self, settings: Settings, hub: Hub, control: RunControl):
        self.settings = settings
        self.hub = hub
        self.control = control

    @property
    def url(self) -> str:
        return f"http://{self.settings.dashboard_host}:{self.settings.dashboard_port}"

    def __enter__(self) -> "Dashboard":
        self.server = Server((self.settings.dashboard_host, self.settings.dashboard_port), make_handler(self.hub, self.control))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.server.shutdown()
        self.server.server_close()


def show(console: Console, e: dict) -> None:
    kind = e["type"]
    if kind == "run":
        console.print(Panel(escape(e["goal"]), title=f"Goal · run {e['run_id']}", border_style="cyan"))
    elif kind == "plan":
        console.print(f"[bold magenta]Planner round {e['round']} · {e['status']}[/] {escape(e['thought'])}")
        if e["plan"]:
            table = Table(show_lines=False)
            table.add_column("#", justify="right")
            table.add_column("Step")
            table.add_column("Expected outcome", style="dim")
            for number, step in enumerate(e["plan"], 1):
                table.add_row(str(number), escape(step["instruction"]), escape(step["expected_outcome"]))
            console.print(table)
        if e["final_assessment"]:
            console.print(Panel(escape(e["final_assessment"]), title="Planner assessment", border_style="magenta"))
    elif kind == "observe":
        console.print(f"[dim]state #{e['iteration']} · {escape(e['title'])} · {escape(e['url'])} · {escape(e.get('shot', ''))}[/]")
    elif kind == "action":
        console.print(f"[blue]▶ {e['name']}[/] {escape(json.dumps(e['args'], ensure_ascii=False))}")
    elif kind == "action_result":
        if e["ok"]:
            console.print(f"[green]  ✓[/] [dim]{escape(e['content'])}[/]")
        else:
            console.print(f"[red]  ✗ tool failed, the executor will adapt:[/] {escape(e['content'])}")
    elif kind == "executor_report":
        console.print(Panel(escape(e["report"]), title="Executor report", border_style="blue"))
    elif kind == "verified":
        if e["complete"]:
            console.print(f"[bold green]✓ Step verified[/] {escape(e['assessment'])}")
        elif e["verdict"] == "retry":
            console.print(f"[bold red]✗ Step NOT complete[/] {escape(e['assessment'])}\n[red]  Retrying the same step with a different approach[/]")
        else:
            console.print(f"[bold red]✗ Step NOT complete[/] {escape(e['assessment'])}\n[red]  Handing back to the planner to re-plan[/]")
        console.print(f"[dim]  {len(e['evidences'])} evidence(s) extracted[/]")
    elif kind == "escalation":
        console.print(f"[magenta]↯ Escalated to planner: {escape(e['reason'])}[/]")
    elif kind == "evidence_check":
        console.print(f"[green]⌁ Evidence check: {e['ok']} verified, {e['failed']} rejected[/]" if e["failed"] == 0 else f"[red]⌁ Evidence check: {e['ok']} verified, {e['failed']} rejected[/]")
        if e.get("rejected"):
            console.print(f"[dim]  rejected quote previews: {[preview[:80] for preview in e['rejected']]}[/]")
    elif kind == "retry":
        console.print(
            f"[yellow]⟳ {escape(e['role'])} failed (attempt {e['attempt']}/{e['max']}): {escape(e['error'])}\n  retrying in {e['wait']}s[/]"
        )
    elif kind == "budget":
        console.print(f"[bold red]{escape(e['message'])}[/]")
    elif kind == "report_reset":
        console.print("\n[bold]Writing the report[/]")
    elif kind == "report_chunk":
        console.out(e["text"], end="", highlight=False)
    elif kind == "report_done":
        console.print(f"\n[bold green]Report saved to {escape(e['path'])}[/]")
    elif kind == "finished":
        console.print(f"[bold green]Finished · {e['status']}[/]")
    elif kind == "error":
        console.print(f"[bold red]✗ Run error: {escape(e['message'])}[/]")


async def run(args: argparse.Namespace) -> None:
    load_dotenv()
    console = Console()
    settings = Settings.from_env()
    mode = resolve_mode(settings)
    check_model_key(settings)
    hub = Hub(settings.dashboard_max_log, mode=mode)
    control = RunControl()
    async with contextlib.AsyncExitStack() as stack:
        if args.checkpointer == "sqlite":
            saver = await stack.enter_async_context(AsyncSqliteSaver.from_conn_string(settings.checkpoint_db))
        else:
            saver = InMemorySaver()
        dashboard = stack.enter_context(Dashboard(settings, hub, control))
        browser = await stack.enter_async_context(BrowserSession(settings))
        ledger = Ledger(on_change=lambda snapshot: hub.publish({"type": "ledger", "data": snapshot}))
        graph = build_graph(settings, build_models(settings, ledger), browser, saver)
        control.loop = asyncio.get_running_loop()

        console.print(f"[cyan]{BANNERS[mode]}[/]")
        console.print(f"[cyan]Dashboard: {dashboard.url}/[/]")
        if settings.dashboard_open:
            webbrowser.open(f"{dashboard.url}/")

        async def run_goal(goal: str, run_id: str, resumed: bool = False) -> None:
            """Drive one goal to completion. A failed or cancelled run
            publishes its outcome and comes back; the server never dies."""

            def safe_show(event: dict) -> None:
                try:
                    show(console, event)
                except Exception:
                    pass  # a console hiccup (legacy encodings) must never abort a run

            def log_line(renderable: object) -> None:
                try:
                    console.print(renderable)
                except Exception:
                    pass

            config = {"configurable": {"thread_id": run_id}, "recursion_limit": settings.recursion_limit}
            control.set_busy(True)
            try:
                if resumed:
                    snapshot = await graph.aget_state(config)
                    if not snapshot.values:
                        log_line(f"[red]No saved run with id {run_id}[/]")
                        return
                    if not snapshot.next:
                        log_line(f"[green]Run {run_id} already finished. Report: {snapshot.values.get('report_path')}[/]")
                        return
                    hub.seed(snapshot.values)
                    log_line(Panel(escape(snapshot.values["goal"]), title=f"Resuming run {run_id}", border_style="cyan"))
                    if snapshot.values.get("browser_url"):
                        await browser.navigate(snapshot.values["browser_url"])
                    payload = None
                else:
                    payload = {"goal": goal, "run_id": run_id, "planner_rounds": 0, "history": [], "status": "running"}
                    event = {"type": "run", "goal": goal, "run_id": run_id}
                    hub.publish(event)
                    safe_show(event)
                log_line(f"[dim]Run id {run_id}. If interrupted, continue with: python runner.py --resume {run_id}[/]")
                async for _, event in graph.astream(payload, config, stream_mode="custom", subgraphs=True):
                    hub.publish(event)
                    safe_show(event)
            except asyncio.CancelledError:
                log_line(f"[yellow]Run {run_id} cancelled[/]")
                event = {"type": "finished", "status": "cancelled"}
                hub.publish(event)
                safe_show(event)
            except Exception as error:
                log_line(f"[bold red]✗ Run {run_id} failed: {type(error).__name__}: {error}[/]")
                hub.publish({"type": "error", "message": f"{type(error).__name__}: {error}"})
            finally:
                control.set_busy(False)
                hub.reset()
                ledger.reset()
                with contextlib.suppress(Exception):
                    await browser.navigate("about:blank")

        async def run_queued(goal: str, run_id: str, resumed: bool) -> asyncio.Task:
            task = asyncio.create_task(run_goal(goal, run_id, resumed))
            control.task = task
            try:
                await task
            finally:
                control.task = None
            return task

        # Resume or CLI goal first (--once exits instead of serving).
        if args.resume:
            await run_queued("", args.resume, True)
            if args.once:
                return
        elif args.goal:
            await run_queued(args.goal, uuid.uuid4().hex[:8], False)
            if args.once:
                return

        # Serve mode: park on the queue until a goal arrives; Ctrl+C exits.
        try:
            while True:
                goal, run_id = await control.queue.get()
                await run_queued(goal, run_id, False)
        except asyncio.CancelledError:
            task = control.task
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="General-purpose agentic browser")
    parser.add_argument("goal", nargs="?", help="Goal in natural language; with no goal the process serves queued goals")
    parser.add_argument("--resume", metavar="RUN_ID", help="Continue an interrupted run from its last checkpoint")
    parser.add_argument("--once", action="store_true", help="Exit after the CLI goal or resume instead of staying in serve mode")
    parser.add_argument("--checkpointer", choices=["sqlite", "memory"], default="sqlite", help="sqlite survives restarts, memory lives only for this process")
    args = parser.parse_args()
    if args.resume and args.checkpointer == "memory":
        parser.error("--resume needs the sqlite checkpointer")
    if args.once and not args.goal and not args.resume:
        parser.error("--once needs a goal or --resume")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(args))


if __name__ == "__main__":
    main()