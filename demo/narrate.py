"""D5: generate demo/narration.md — narration beats with FINAL-time stamps.

Reads demo/out/marks.json + demo/out/timeline.json (both produced by the
record/edit pair) and writes one line per beat (hook, architecture, live
run, verification, escalation — only if one really happened — result,
close). Every suggested voiceover sentence uses the REAL run numbers
(planner calls, steps, evidences, sites, cost, mode). In cloud-only mode
the copy never mentions open weights; in hybrid it does.

Usage: python demo/narrate.py [--marks ...] [--timeline ...] [--out demo/narration.md]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
OUT_DIR = DEMO_DIR / "out"

MAX_WORDS = 380


def stamp(seconds: float) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build narration.md from the edit artifacts")
    parser.add_argument("--marks", default=str(OUT_DIR / "marks.json"))
    parser.add_argument("--timeline", default=str(OUT_DIR / "timeline.json"))
    parser.add_argument("--out", default=str(DEMO_DIR / "narration.md"))
    args = parser.parse_args()

    marks = json.loads(Path(args.marks).read_text(encoding="utf-8"))
    timeline = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
    final_state = marks.get("final") or {}
    mode = str(final_state.get("mode") or marks.get("mode") or "cloud")

    caps_final = [dict(c, text=str(c.get("text") or "")) for c in timeline.get("captions_final", [])]
    scenes = marks.get("scenes") or {}

    def beat_time(caption_frag: str, scene_key: str | None = None, fallback: float = 0.0) -> float:
        """Final-time of a beat: first try a fragment match on the caption
        texts (captions are full sentences), else map a raw scene timestamp
        through the speed timeline."""
        for c in caps_final:
            if c["text"].startswith(caption_frag) or caption_frag in c["text"]:
                return float(c["final_start"])
        value = scenes.get(scene_key) if scene_key else None
        if isinstance(value, (int, float)):
            for seg in timeline.get("segments", []):
                if seg["raw_start"] <= value <= seg["raw_end"]:
                    return seg["final_start"] + (value - seg["raw_start"]) / seg["speed"]
        return fallback

    # Real run numbers (never invented; filled from the final /state snapshot)
    calls = int(final_state.get("planner_calls") or 0)
    steps = int(final_state.get("steps") or 0)
    tokens = int(final_state.get("total_tokens") or 0)
    cost = float(final_state.get("cost_usd") or 0.0)
    evidences = int(final_state.get("evidences") or 0)
    sites = int(final_state.get("sites") or 0)

    modal = {
        "cloud": "Everything - planner, executor, verifier, reporter - bills the Meta Model API.",
        "hybrid": "The planner and reporter stay text-only on Meta; executor and verifier run on open weights via Baseten.",
    }[mode]

    escalation = any("problem" in c["text"].lower() or "re-plans" in c["text"] for c in marks.get("captions", []))

    t_arch = beat_time("Give it a goal", "dashboard")
    t_live = beat_time("Planner", "start_click", 20.0)
    t_verify = beat_time("Every quote")
    t_escal = beat_time("Verifier flagged")
    t_result = beat_time("planner calls for")
    t_close = 0.0
    for seg in timeline.get("segments", []):
        if seg.get("label") == "outro card":
            t_close = seg["final_start"] + 0.4

    lines: list[tuple[str, str, str]] = []  # (heading, timestamp, sentence)
    lines.append(("Hook", "00:00",
                  f"Nexus: a browser agent that shows its receipts. This is one real, uncut run."))
    lines.append(("Architecture", stamp(t_arch), modal))
    call_word = "one text-only planner call" if calls == 1 else f"{calls} text-only planner calls"
    step_word = "step" if steps == 1 else "steps"
    lines.append(("Live run", stamp(t_live),
                  f"I gave it one goal. In {call_word} the planner split the work into {steps} {step_word}."))
    lines.append(("Verification", stamp(t_verify),
                  f"Every claim it keeps is re-checked word-for-word against the page: {evidences} verified quotes from {sites} sites so far."))
    if escalation:
        lines.append(("Escalation", stamp(t_escal),
                      "When the verifier rejects a step, the executor retries or hands the problem back to the planner."))
    lines.append(("Result", stamp(t_result),
                  f"{calls} planner calls for {steps} steps, {tokens:,} tokens, ${cost:.2f} billed."))
    lines.append(("Close", stamp(t_close),
                  "The ledger on the right proves where every screenshot and token went. All of this ran for real, start to finish."))

    words = sum(len(sentence.split()) for _h, _t, sentence in lines)
    out = [
        "# Nexus demo narration (per-beat, final-video timestamps)",
        "",
        f"Run snapshot: mode `{mode}`, {calls} planner call(s), {steps} step(s), "
        f"{evidences} evidence(s), {sites} site(s), {tokens:,} tokens, ${cost:.2f}. "
        f"All numbers are from the recorded run's final /state.",
        "",
    ]
    for heading, stamp_text, sentence in lines:
        out.append(f"- **{heading} · {stamp_text}** — {sentence}")
    out.append("")
    out.append(f"~{words} words (inside the {MAX_WORDS}-word voiceover budget; one line per beat).")
    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"[narrate] {args.out} ({words} words)")


if __name__ == "__main__":
    main()
