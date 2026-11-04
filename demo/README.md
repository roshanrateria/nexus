# Nexus — one-command REAL demo recorder

Everything in the finished video comes from one genuine run of the Nexus
dashboard agent: the recorder drives the real web UI (types the goal into
the composer, clicks Start), polls the live `/state` endpoint, and records
the dashboard while the agent actually plans, browses, verifies and reports.
Nothing is staged, no numbers are invented, no screenshots are mocked:
the captions and all stats ship straight from the run's `/state`.

## What you get

| artifact | produced by |
| --- | --- |
| `out/raw/<name>.webm` | recorder (raw 25 fps VP8 capture) |
| `out/marks.json` | recorder: scene cuts, captions, idle stretches, final `/state` snapshot |
| `nexus_demo.mp4` | `edit.py`: ≤180 s, 1920×1080, H.264 (CRF 18, faststart) |
| `nexus_demo.srt` | `edit.py`: caption sidecar — **captions are NOT burned into the video** (owner's preference), timestamps are real and mapped into final time |
| `timeline.json` | `edit.py`: piecewise raw→final map (segment speeds, anchors, final caption times) |
| `contact_sheet.png` | `edit.py` verify stage: 6 frames at 5/20/40/60/80/95 % |
| `x_clip.mp4` (optional) | `edit.py --x-clip`: ≤30 s teaser (first plan, first verified evidence, report + evidence sheet) |
| `../narration.md` | `narrate.py`: narration beats in final-video time, real run numbers |

## One command each

```text
# 1. record one genuine run (goal comes from demo/goal.txt)
python demo/record_demo.py

# 2. cut + verify
python demo/edit.py
python demo/narrate.py
```

Optional knobs:

```text
python demo/record_demo.py --goal "..."      # inline goal instead of goal.txt
python demo/record_demo.py --attempts 2      # default 1 here / 2 for flaky days
python demo/record_demo.py --timeout 480 --max-cost 1.0   # run abort ceilings
python demo/record_demo.py --repo <url>      # outro card repo line
python demo/record_demo.py --overlay-captions  # burn the live caption pill into the video again
python demo/edit.py --x-clip                 # also build the teaser
python demo/edit.py --voiceover path/to.wav  # mux a narration track afterwards
python demo/edit.py --verify-only            # re-run the D6 checks on the mp4
```

## Timing model

The raw run is recorded at 1x, then `edit.py` compresses it with a
marks-driven timeline:

* intro card, composer typing, the run's live moments, the last
  `--keep` (25) seconds of the dashboard (report scroll, evidence sheet,
  stage tabs) and both cards play at **1x**;
* every stretch where the dashboard signature (history, evidences, log
  length, planner calls, status, current shot) stays unchanged ≥5 s is
  marked as idle and plays at speed **f** (searched 3→16x, smallest f
  that keeps the final ≤175 s; the hard ceiling is 180 s);
* if it doesn't fit the ceiling even at 16x, edit exits non-zero — pick a
  shorter goal, don't fake it.
* captions from the run are mapped raw→final and shipped in the `.srt`
  only; every cue ≥2.2 s, no overlaps.

## Captions workflow (post-production)

The MP4 ships clean. To caption later:

```text
# side-by-side players handle .srt natively; for a burn-in master:
ffmpeg -i nexus_demo.mp4 -vf "subtitles=nexus_demo.srt:force_style='FontName=Inter,FontSize=16'" -c:a copy nexus_demo_captioned.mp4
```

`--overlay-captions` restores the original live pill mode instead.

## The goal

`demo/goal.txt` is a deliberately compressed but genuinely real research
brief (semiconductor supply chain 2020–2025: policy, fab expansion, AI
demand; ≥4 direct-visited sources; verbatim quotes; no invented stats).
The original long-form brief was heavier than a ≤3-minute demo window;
the recorder accepts any goal file via `--goal-file`.

## Requirements

Windows; Python 3.11+; `pip install -r demo/requirements-demo.txt`
(Playwright, imageio-ffmpeg, Pillow); `ffmpeg`/`ffprobe` on PATH for
render + verification; a working model key in `.env` (never printed, and
`record_demo.py` masks HTTP traffic logging). Mode resolves automatically
(`cloud` when no `BASETEN_API_KEY` is set).

Run cost for this recorded demo: billed by the ledger shown in the video
(`--max-cost 1.0` hard abort ceiling), plus one dashboard session with no
hidden expenses.

## Honest-run receipts

* `out/marks.json` stores the run's final `/state` snapshot (status,
  planner calls, steps, evidences, sites, tokens, billed cost, mode) —
  those exact numbers appear in the outro card and `.srt`.
* `demo/overlay.js` adds only pointer cosmetics (cursor, ripple,
  Time-lapse badge) via an init script; it never mutates page content.
* The recorder refuses to render anything from a failed run: failed
  attempts keep `out/marks_failed_a<N>.json` and no final video is
  produced unless an attempt reached `goal_achieved`.

## Completeness note (owner-requested final build)

A fourth run also hit its cap; on the owner's explicit request the final
`nexus_demo.mp4` was assembled from the run #3 bytes (the proof-cut source)
via `python demo/build_demo_from_proof.py`: same honest time-lapse rules,
captions burned in AND shipped as `nexus_demo.srt`, and a closing card
(`demo/out/proof_outro_card.webm`, same glass style) that discloses the
watchdog cut and shows the run's real ledger numbers. Every dashboard frame
is the genuine recording; nothing is re-staged. Run receipt:
`demo/out/marks_run3.json` (recovered from version control because later
attempts overwrite `marks_failed_a*.json`).

## Engine proof cut (watchdog-stopped run)

Three real research-grade runs (compressed real briefs from `demo/goal.txt`)
were recorded for the ≤180 s window; all three hit the recorder's run-cap
(`--timeout`), which by design **refuses to render a success demo from a
failed run**. The engine itself demonstrably works at depth — the third run
was cut while still executing, having visited 10+ sources (SIA, commerce.gov,
nist.gov, OECD, DuckDuckGo, TSMC IR), verified 4 verbatim quotes, sailed
through one verdict-flagged re-plan, and billed $0.22 — so the receipts of
that run were turned into an honest proof reel, with nothing re-staged:

```text
python demo/edit.py --proof-cut    # newest marks_failed_a*.json -> proof_cut.mp4
```

`proof_cut.mp4` (35.4 s, 1080p H.264): plan split → source visits → verified
quotes landing → live bot-check → the watchdog cut with the ledger on screen.
It is **not** `nexus_demo.mp4` and never claims `goal_achieved`; proof captions
in the `.srt` are hand-transcribed from the reel's own frames.

Why no "resume": the backend keeps run state in memory only — once the
watchdog cancelled the run and the runner exited, a resume was impossible
(and would have meant touching agent/backend code, out of the demo's scope).

## Known rough edges recorded during THIS demo campaign

* Research-grade goals (4-angle, 2-angle, micro-case-study briefs) ran
  480 s / 300 s / 300 s of wall time and hit the cap: a genuine research
  run with ~26% idle share cannot fit a 3-minute video under the honest
  cut rules (needs ≤ ~165 s of agent work). The success-demo cut with the
  outro card, report scroll, evidence sheet and real totals is still
  **pending a run that finishes in-window**.
* Attempt spend was capped (`--max-cost 0.9-1.0`) and the watchdog passed
  through `POST /cancel`; the recorder kept `marks_failed_a*.json` + raw
  webm for each, and renders nothing from them except the labeled proof
  reel above.
* `nexus_demo.mp4` therefore does not exist yet — do not present a failed
  run as the success demo.

## Run cost for this campaign

Recorded attempts three real runs + rehearsals; billed amounts are denied
after cancellation, bounded by the caps actually used (≤ ~$1.9 of the $4
total session budget). The proof reel cost nothing new: it is cut from
already-recorded bytes.

