"""Benchmark runner for bench/tasks.yml under one mode profile.

Usage:
    python bench/run_bench.py --profile hybrid [--limit N]

The profile file (profiles/<name>.env) is applied AFTER .env so its mode and
role variables win; BROWSER_HEADLESS is forced to true. Every task runs in its
own fresh graph, browser session and Privacy Ledger. Each task records: id,
goal, success, wall seconds, steps verified, planner calls and the ledger
snapshot. Success = every must_contain regex matches the final report
case-insensitively. Results go to bench/results/<profile>.json and the
cross-profile table to bench/summary.md. Never prints credentials.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "bench" / "results"
ROLES = ("planner", "executor", "verifier", "reporter")
PROFILE_KEYS = sorted(
    {"NEXUS_MODE", *{f"{role}_{kind}".upper() for role in ROLES for kind in ("model", "reasoning_effort", "max_tokens")}}
)


def load_profile(name: str) -> dict[str, str]:
    """Apply profiles/<name>.env over the environment (after .env, so it wins)."""
    path = ROOT / "profiles" / f"{name}.env"
    if not path.is_file():
        raise SystemExit(f"Unknown profile {name!r}: {path} does not exist")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    unexpected = sorted(set(values) - set(PROFILE_KEYS))
    if set(values) != set(PROFILE_KEYS):
        raise SystemExit(
            f"profile {path.name} must contain exactly NEXUS_MODE plus the 12 role variables"
            f" (model, reasoning_effort, max_tokens per role); missing={sorted(set(PROFILE_KEYS) - set(values))},"
            f" unexpected={unexpected}"
        )
    os.environ.update(values)
    os.environ["BROWSER_HEADLESS"] = "true"
    return values


def load_tasks() -> list[dict]:
    import yaml

    tasks = yaml.safe_load((ROOT / "bench" / "tasks.yml").read_text(encoding="utf-8"))["tasks"]
    for task in tasks:
        for pattern in task["must_contain"]:
            re.compile(pattern, re.IGNORECASE)  # fail fast on bad regex
    return tasks


async def run_task(task: dict, settings) -> dict:
    from agent import BrowserSession, build_graph, build_models
    from langgraph.checkpoint.memory import InMemorySaver
    from ledger import Ledger

    started = time.monotonic()
    ledger = Ledger()
    report_text = ""
    steps = 0
    run_id = uuid.uuid4().hex[:8]
    try:
        async with BrowserSession(settings) as browser:
            graph = build_graph(settings, build_models(settings, ledger), browser, InMemorySaver())
            config = {"configurable": {"thread_id": run_id}, "recursion_limit": settings.recursion_limit}
            payload = {"goal": task["goal"], "run_id": run_id, "planner_rounds": 0, "history": [], "status": "running"}
            async for _, event in graph.astream(payload, config, stream_mode="custom", subgraphs=True):
                kind = event.get("type")
                if kind == "verified":
                    steps += 1
                elif kind == "report_chunk":
                    report_text += event["text"]
                elif kind == "report_done" and not report_text.strip():
                    report_text = Path(event["path"]).read_text(encoding="utf-8")
    except Exception as error:  # one broken task must never kill the bench
        return {
            "id": task["id"],
            "goal": task["goal"],
            "success": False,
            "error": f"{type(error).__name__}: {error}"[:300],
            "wall_seconds": round(time.monotonic() - started, 1),
            "steps": steps,
            "planner_calls": ledger.snapshot()["planner_calls"],
            "ledger": ledger.snapshot(),
        }

    missing = [pattern for pattern in task["must_contain"] if not re.search(pattern, report_text, re.IGNORECASE)]
    return {
        "id": task["id"],
        "goal": task["goal"],
        "success": not missing and bool(report_text.strip()),
        "missing_patterns": missing,
        "report_chars": len(report_text),
        "wall_seconds": round(time.monotonic() - started, 1),
        "steps": steps,
        "planner_calls": ledger.snapshot()["planner_calls"],
        "ledger": ledger.snapshot(),
    }


def summarize_profile(profile: str, records: list[dict]) -> dict:
    """Aggregate the per-task ledgers into one profile-level summary."""
    totals = {endpoint: dict.fromkeys(("calls", "prompt_tokens", "completion_tokens", "bytes_out", "images_out"), 0) for endpoint in ("cloud", "open")}
    for record in records:
        snapshot = record.get("ledger") or {}
        for endpoint in totals:
            for key in totals[endpoint]:
                totals[endpoint][key] += int((snapshot.get(endpoint) or {}).get(key, 0))
    tokens = totals["cloud"]["prompt_tokens"] + totals["cloud"]["completion_tokens"]
    open_tokens = totals["open"]["prompt_tokens"] + totals["open"]["completion_tokens"]
    successes = sum(1 for record in records if record["success"])
    return {
        "profile": profile,
        "tasks": len(records),
        "successes": successes,
        "success_rate": f"{successes}/{len(records)}" if records else "0/0",
        "cloud_tokens": tokens,
        "open_tokens": open_tokens,
        "open_token_share": round(open_tokens / (tokens + open_tokens), 4) if (tokens + open_tokens) else 0.0,
        "images_to_cloud": totals["cloud"]["images_out"],
        "wall_seconds": round(sum(record["wall_seconds"] for record in records), 1),
        "planner_calls": sum(record["planner_calls"] for record in records),
    }


def write_summary(current: dict) -> list[dict]:
    """Rewrite bench/summary.md from every profile recorded in bench/results/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summaries = [current]
    for path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if data.get("profile") != current["profile"]:
            summaries.append(data.get("summary") or {})
    summaries = [entry for entry in summaries if entry.get("profile") and entry.get("tasks")]
    summaries = sorted({entry["profile"]: entry for entry in summaries}.values(), key=lambda entry: entry["profile"].lower())

    lines = [
        "# Benchmark summary",
        "",
        "Regenerated by `bench/run_bench.py --profile <name>`; per-profile totals over all tasks.",
        "",
        "| Profile | Success rate | Cloud tokens | Open token share | Images to cloud | Wall (s) |",
        "|---|---|---|---|---|---|",
    ]
    for entry in summaries:
        lines.append(
            f"| {entry['profile']} | {entry['success_rate']} ({entry['successes']}/{entry['tasks']}) | "
            f"{entry['cloud_tokens']} | {entry['open_token_share']} | {entry['images_to_cloud']} | {entry['wall_seconds']} |"
        )
    (ROOT / "bench" / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", required=True, help="profile name in profiles/, e.g. hybrid")
    parser.add_argument("--limit", type=int, default=None, help="run only the first N tasks")
    args = parser.parse_args()

    from dotenv import load_dotenv
    from rich.console import Console
    from rich.table import Table

    from schemas import Settings

    console = Console()
    load_dotenv(ROOT / ".env")
    load_profile(args.profile)
    settings = Settings.from_env()
    tasks = load_tasks()
    if args.limit:
        tasks = tasks[: args.limit]

    records = []
    for task in tasks:
        console.print(f"[cyan]-- {task['id']}:[/] {task['goal'][:90]}...")
        record = asyncio.run(run_task(task, settings))
        records.append(record)
        status = "[green]SUCCESS[/]" if record["success"] else f"[red]FAIL[/] ({record.get('error') or record.get('missing_patterns')})"
        console.print(f"   {status} in {record['wall_seconds']}s after {record['steps']} step(s), {record['planner_calls']} planner call(s)")

    summary = summarize_profile(args.profile, records)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{args.profile}.json").write_text(
        json.dumps({"profile": args.profile, "generated": datetime.now(timezone.utc).isoformat(), "summary": summary, "tasks": records}, indent=2),
        encoding="utf-8",
    )
    entries = write_summary(summary)

    table = Table(title="Bench summary")
    for column in ("profile", "success", "cloud tokens", "open share", "images to cloud", "wall (s)"):
        table.add_column(column)
    for entry in entries:
        table.add_row(entry["profile"], entry["success_rate"], str(entry["cloud_tokens"]), str(entry["open_token_share"]), str(entry["images_to_cloud"]), str(entry["wall_seconds"]))
    console.print(table)
    console.print(f"Results: {RESULTS_DIR / (args.profile + '.json')} -- table: bench/summary.md")


if __name__ == "__main__":
    main()
