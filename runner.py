import argparse
import asyncio
import contextlib
import json
import queue
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from agent import BrowserSession, build_graph, build_models
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
    s.evidences.forEach((e, i) => {
      const d = el('details');
      d.append(el('summary', '', '[' + (i + 1) + '] ' + e.summarized), el('div', 'dim mono', e.url), el('pre', '', e.original_text));
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


class Hub:
    def __init__(self, max_log: int):
        self.max_log = max_log
        self.lock = threading.Lock()
        self.subscribers: list[queue.Queue] = []
        self.state: dict = {
            "goal": "",
            "run_id": "",
            "status": "starting",
            "outcome": "",
            "thought": "",
            "plan": [],
            "history": [],
            "evidences": [],
            "current": {},
            "log": [],
            "report": "",
            "report_path": "",
            "ledger": {},
        }

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
            s["current"].update(iteration=e["iteration"], url=e["url"], title=e["title"])
        elif kind == "action":
            s["current"]["last_action"] = f"{e['name']}({json.dumps(e['args'], ensure_ascii=False)})"
            self.note("action", s["current"]["last_action"])
        elif kind == "action_result":
            self.note("ok" if e["ok"] else "error", f"{e['name']}: {e['content']}")
        elif kind == "executor_report":
            s["current"]["report"] = e["report"]
            self.note("action", "Executor reported back")
        elif kind == "verified":
            s["history"].append(e)
            s["evidences"].extend(e["evidences"])
            verdict = {"done": "Step verified", "retry": "Step NOT complete, retrying locally", "replan": "Step NOT complete, escalating to planner"}[e["verdict"]]
            self.note("ok" if e["complete"] else "failed", f"{verdict}: {e['assessment']}")
        elif kind == "escalation":
            self.note("plan", f"Escalated to the planner: {e['reason']}")
        elif kind == "evidence_check":
            self.note("ok" if e["failed"] == 0 else "failed", f"Evidence check: {e['ok']} ok, {e['failed']} dropped")
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
        elif kind == "finished":
            s.update(status="done", outcome=e["status"], current={})


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        return None


def make_handler(hub: Hub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            return None

        def do_GET(self) -> None:
            if self.path == "/events":
                self.stream()
            else:
                self.page()

        def page(self) -> None:
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def stream(self) -> None:
            self.send_response(200)
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
    def __init__(self, settings: Settings, hub: Hub):
        self.settings = settings
        self.hub = hub

    @property
    def url(self) -> str:
        return f"http://{self.settings.dashboard_host}:{self.settings.dashboard_port}"

    def __enter__(self) -> "Dashboard":
        self.server = Server((self.settings.dashboard_host, self.settings.dashboard_port), make_handler(self.hub))
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
        console.print(f"[dim]state #{e['iteration']} · {escape(e['title'])} · {escape(e['url'])}[/]")
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
        console.print(f"[magenta]↯ Escalated to the planner: {escape(e['reason'])}[/]")
    elif kind == "evidence_check":
        console.print(f"[green]⌁ Evidence check: {e['ok']} ok, {e['failed']} dropped[/]" if e["failed"] == 0 else f"[red]⌁ Evidence check: {e['ok']} ok, {e['failed']} dropped[/]")
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


async def run(args: argparse.Namespace) -> None:
    load_dotenv()
    settings = Settings.from_env()
    console = Console()
    hub = Hub(settings.dashboard_max_log)
    async with contextlib.AsyncExitStack() as stack:
        if args.checkpointer == "sqlite":
            saver = await stack.enter_async_context(AsyncSqliteSaver.from_conn_string(settings.checkpoint_db))
        else:
            saver = InMemorySaver()
        dashboard = stack.enter_context(Dashboard(settings, hub))
        browser = await stack.enter_async_context(BrowserSession(settings))
        ledger = Ledger(on_change=lambda snapshot: hub.publish({"type": "ledger", "data": snapshot}))
        graph = build_graph(settings, build_models(settings, ledger), browser, saver)
        console.print(f"[cyan]Dashboard: {dashboard.url}[/]")
        if settings.dashboard_open:
            webbrowser.open(dashboard.url)
        if args.resume:
            run_id = args.resume
            config = {"configurable": {"thread_id": run_id}, "recursion_limit": settings.recursion_limit}
            snapshot = await graph.aget_state(config)
            if not snapshot.values:
                raise SystemExit(f"No saved run with id {run_id}")
            if not snapshot.next:
                console.print(f"[green]Run {run_id} already finished. Report: {snapshot.values.get('report_path')}[/]")
                return
            hub.seed(snapshot.values)
            console.print(Panel(escape(snapshot.values["goal"]), title=f"Resuming run {run_id}", border_style="cyan"))
            if snapshot.values.get("browser_url"):
                await browser.navigate(snapshot.values["browser_url"])
            payload = None
        else:
            goal = args.goal or console.input("[bold cyan]Goal › [/]")
            run_id = uuid.uuid4().hex[:8]
            config = {"configurable": {"thread_id": run_id}, "recursion_limit": settings.recursion_limit}
            payload = {"goal": goal, "run_id": run_id, "planner_rounds": 0, "history": [], "status": "running"}
            event = {"type": "run", "goal": goal, "run_id": run_id}
            hub.publish(event)
            show(console, event)
        console.print(f"[dim]Run id {run_id}. If interrupted, continue with: python runner.py --resume {run_id}[/]")
        async for _, event in graph.astream(payload, config, stream_mode="custom", subgraphs=True):
            hub.publish(event)
            show(console, event)


def main() -> None:
    parser = argparse.ArgumentParser(description="General-purpose agentic browser")
    parser.add_argument("goal", nargs="?", help="Goal in natural language; asked interactively when omitted")
    parser.add_argument("--resume", metavar="RUN_ID", help="Continue an interrupted run from its last checkpoint")
    parser.add_argument("--checkpointer", choices=["sqlite", "memory"], default="sqlite", help="sqlite survives restarts, memory lives only for this process")
    args = parser.parse_args()
    if args.resume and args.checkpointer == "memory":
        parser.error("--resume needs the sqlite checkpointer")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(args))


if __name__ == "__main__":
    main()