# Demo rehearsal record

Mode: **cloud-only** (no `BASETEN_API_KEY` in `.env`) — all four roles on Meta
`muse-spark-1.3`, screenshots included in the executor/verifier payloads.
Runner limits per rehearsal: 8-minute per-run budget ($1.00 cap), headless,
`RATE_LIMIT_RPM=35`. Every number below is from a live run against the real
API (artifacts in `runs/<id>/check.json`, reports in `reports/`).

## Chosen demo goal (`demo/goal.txt`)

> Find the latest stable releases of Python, Node.js and Go. For each give the
> version number and release date, with a source link.

## Results

| Run | Wall | Cost | Plan steps | Evidences | Distinct hosts | Status | Verdict |
|---|---|---|---|---|---|---|---|
| `3d8d5bd1` | 158 s | $0.2480 | 3 | 10 | python.org, nodejs.org, go.dev | goal_achieved | PASS (11/11 gates) |
| `85768127` | 169 s | $0.2337 | 3 | 18 | python.org, nodejs.org, go.dev | goal_achieved | PASS (11/11 gates) |

Both repeats meet every demo criterion: wall 90–240 s, ≥ 3 distinct sites,
≥ 4 evidences, cost well under the $1.00 per-run cap. Run `85768127` also
exercised a per-step retry → replan → goal_achieved cycle on the way
(14 recorded timeline events), which shows recovery behavior live.

## Fact verification (report vs live source pages, 2026-11-04)

| Claim in the report | Live page check | Verdict |
|---|---|---|
| Python 3.15.2, Oct. 25, 2026 | python.org/downloads release table row "Python 3.15.2 — Oct. 25, 2026" | **correct** |
| Node.js v26.13.0 LTS, 2026-10-28 | nodejs.org/en/blog/release/v26.13.0 — "2026-10-28, Version 26.13.0 'Lithium' (LTS)" | **correct** |
| Go 1.27.3, 2026-10-19 | go.dev/dl lists go1.27.3 as latest stable; go.dev/doc/devel/release dates go1.27.3 2026-10-19 | **correct** |

Wrong facts found by the human check: **none**. Cosmetic only: the report body
quotes source text with proper UTF-8 curly quotes (verified U+201C); terminal
rendering makes them look garbled in PowerShell only.

## Other candidate goals (not chosen)

| Goal | Status |
|---|---|
| "What are the three most recent stable Rust releases? Give version numbers and release dates, with sources." | Repeat 1 PASS (`10c4631b`, 139 s, $0.1585). Repeat 2 timed out at the 480 s budget in a per-step retry stall on blog.rust-lang.org (`af25d0f7`, $0.5012, no report). A fresh-profile retry attempt was aborted (harness shell lost before starting). |
| "Find the current stable version of PostgreSQL and the end-of-life date of the oldest supported major version, with sources." | Not rehearsed (no runs). |

## How to run the demo

```bash
python runner.py              # serve mode, then open http://127.0.0.1:8765/
# paste the goal above into the composer and press Start
```

Headless verification of the same flow exists as `python scripts/run_check.py --goal "$(Get-Content demo\goal.txt -Raw)"` and the browser-level E2E as `python scripts/ui_check.py`.
