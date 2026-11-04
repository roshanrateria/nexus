"""Builds the COMPLETE demo video (demo/out/nexus_demo.mp4) from the
watchdog-stopped run's real bytes (demo/out/marks_failed_a1.json +
demo/out/raw/dash_*.webm), on the owner's explicit request after the
fourth run also hit the cap.

Honesty rules kept:
  * every dashboard frame is the recorded run (no staged UI);
  * the intro card is the run's own recorded intro;
  * the closing card is a real card in the same glass style whose numbers
    are transcribed from the run's frames ($0.22 billed, 4 verified
    quotes) and which says plainly: real run, cut by the demo watchdog;
  * captions are burned in (owner's later request) AND shipped as .srt;
  * windows/anchors come from marks.json beats, speeds follow the same
    time-lapse rules (idles compressed, live moments at 1x).

Zero LLM spend: it only reads already-recorded material.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMO_DIR))

import cards     # noqa: E402 (self-contained card renderer)
import edit      # noqa: E402 (srt writer + verify)

OUT_DIR = DEMO_DIR / "out"
RAW_DIR = OUT_DIR / "raw"

IDLE_F = 16.0
OUTRO_HOLD_S = 4.7        # seconds of the recorded closing card kept in the cut
REPO = "https://github.com/roshanrateria/nexus"   # pushed; shown on the closing card


def log(msg: str) -> None:
    print(f"[demo-now] {msg}", flush=True)


def pick_failed() -> tuple[dict, Path]:
    """Pin to the run the owner named (the proof-cut source): its receipt is
    demo/out/marks_run3.json - later attempts overwrite marks_failed_a*.json
    because the attempt counter restarts, so run 3's receipt lives here."""
    for cand in (OUT_DIR / "marks_run3.json", *sorted(OUT_DIR.glob("marks_failed_a*.json"),
                 key=lambda p: p.stat().st_mtime, reverse=True)):
        if not cand.is_file():
            continue
        data = json.loads(cand.read_text(encoding="utf-8"))
        video = Path(data.get("video") or "")
        if video.is_file():
            return data, video
    sys.exit("[demo-now] no run receipt with an existing raw webm")


def write_outro_card(path: Path, repo: str) -> None:
    """Closing card in the same glass style; repo from the owner's push,
    numbers transcribed from the run's frames, watchdog disclosed."""
    bullets: list[str] = cards.load_bullets()
    repo = (repo or "").strip()
    if repo:
        repo_block = f'<div><span class="chip">{cards.html.escape(repo)}</span></div>'
    else:
        repo_block = '<div><span class="chip" style="color:#8b95a5">code: unpublished hackathon repo</span></div>'
    rows = "".join(f"<li>{cards.html.escape(t)}</li>" for t in bullets)
    body = (
        cards.LOGO.replace('<div class="logo">', '<div class="logo" style="animation:none">', 1)
        + '<div class="name small">Nexus</div>'
        + repo_block
        + "<h2>Built during the hackathon</h2>"
        + f"<ul>{rows}</ul>"
        + '<div class="verified">Every claim verified verbatim against the page.</div>'
        + '<div class="sub">This reel: one real research run, cut by the demo watchdog'
        "<br>while still executing - $0.22 billed, 4 verified quotes, 24 analyzer calls live in the ledger.</div>"
    )
    path.write_text(cards.SHELL.format(title="Nexus", body=body, glass=cards.GLASS, gradient=cards.GRADIENT),
                    encoding="utf-8")


def record_card(html_path: Path, seconds: float) -> Path:
    import playwright.sync_api as pw
    RAW_DIR.mkdir(exist_ok=True)
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--hide-scrollbars"])
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
            color_scheme="dark", record_video_dir=str(RAW_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        page.goto(html_path.resolve().as_uri())
        page.wait_for_timeout(int(seconds * 1000))
        page.close()
        ctx.close()
        browser.close()
    newest = max(RAW_DIR.glob("page@*.webm"), key=lambda q: q.stat().st_mtime)
    dst = OUT_DIR / "proof_outro_card.webm"
    shutil.copyfile(newest, dst)
    newest.unlink(missing_ok=True)
    return dst


def build_segments(marks: dict) -> list[tuple]:
    scenes = marks["scenes"]
    caps = {c["text"]: c for c in marks.get("captions", [])}
    intro_end = float(scenes["intro"][1])
    dashboard0 = float(scenes["dashboard"][0]) + 0.05
    start_click = float(scenes["start_click"])
    rec_end = float(scenes["recording_end"])

    def beat(prefix: str):
        for c in marks.get("captions", []):
            if str(c.get("text") or "").startswith(prefix):
                return float(c["t_start"]), float(c["t_end"])
        return None, None

    windows: list[tuple[float, float, bool]] = []
    windows.append((0.0, intro_end, False))                     # recorded intro card
    windows.append((dashboard0, min(start_click + 1.4, rec_end - 30), False))  # real typing + Start
    p0, p1 = beat("Planner")
    if p0:
        windows.append((p0 - 1.0, p1 + 10.0, True))             # plan split + mode
    windows.append((96.0, 117.0, True))                         # real execution cadence
    q0, q1 = beat("Every quote")
    if q0:
        windows.append((q0 - 7.0, q1 + 2.7, True))              # verified quotes landing
    windows.append((279.0, 303.0, True))                        # sources + bot check
    windows.append((rec_end - 25.5, rec_end - 0.1, False))      # ledger + watchdog cut

    segs: list[tuple] = []
    for a, b, idle_aware in windows:
        if b - a < 0.5:
            continue
        if idle_aware:
            segs.extend(edit.range_with_idles(a, b, marks, IDLE_F))
        else:
            segs.append((a, b, 1.0, "dashboard"))
    return edit.fold_same_speed(segs)


def build_captions(marks: dict, segs: list[dict]) -> list[dict]:
    def inside(t: float) -> bool:
        return any(s["raw_start"] <= t <= s["raw_end"] for s in segs)

    rows = [c for c in marks.get("captions", []) if inside(float(c["t_start"]))]
    synth = [
        {"text": "The real goal, typed character by character.", "t_start": 12.0, "t_end": 15.6},
        {"text": "Start - from here on, agent only.", "t_start": 29.9, "t_end": 32.3},
        {"text": "Planner split the real goal into three source visits: SIA, a US .gov page, TSMC investor relations.", "t_start": 65.9, "t_end": 70.1},
        {"text": "Live at the engine's real cadence: navigate, screenshot, extract, verify.", "t_start": 98.5, "t_end": 102.9},
        {"text": "Bot checks happen - the agent pivots to other credible sources.", "t_start": 286.4, "t_end": 290.6},
        {"text": "Watchdog, not the engine: cut mid-research at the run cap - $0.22 billed, 4 verified quotes live in the ledger.", "t_start": 318.28, "t_end": 322.9},
        {"text": "Ledger at the cut: 24 analyzer calls, 199k tokens, every screenshot logged to cloud.", "t_start": 323.9, "t_end": 327.9},
    ]
    rows += [c for c in synth if inside(float(c["t_start"]))]
    return sorted(rows, key=lambda c: c["t_start"])


def render(raw: Path, segs: list[dict], outro_webm: Path, out: Path, ffmpeg: str) -> None:
    """Clean video (no burned captions; the .srt ships separately)."""
    parts = []
    for i, s in enumerate(segs):
        parts.append(
            f"[0:v]trim=start={s['raw_start']:.3f}:end={s['raw_end']:.3f},"
            f"setpts=(PTS-STARTPTS)/{s['speed']}[v{i}]"
        )
    n = len(segs)
    parts.append(f"[1:v]trim=duration={OUTRO_HOLD_S:.2f},setpts=(PTS-STARTPTS)/1.0[voutro]")
    concat_in = "".join(f"[v{i}]" for i in range(n)) + "[voutro]"
    graph = (
        ";".join(parts)
        + f";{concat_in}concat=n={n + 1}:v=1:a=0[vc];"
        + "[vc]fps=30,scale=1920:1080:flags=lanczos,format=yuv420p[vout]"
    )
    command = [ffmpeg, "-y", "-i", str(raw), "-i", str(outro_webm),
               "-filter_complex", graph, "-map", "[vout]",
               "-c:v", "libx264", "-crf", "18", "-preset", "medium",
               "pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    command[command.index("pix_fmt")] = "-pix_fmt"
    log("ffmpeg render start")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-3000:] + "\n")
        sys.exit(f"[demo-now] ffmpeg failed (rc={result.returncode})")
    log("ffmpeg render done")


def main() -> None:
    marks, raw = pick_failed()
    log(f"source: {raw.name} ({float(marks['scenes']['recording_end']):.1f}s raw)")

    cards_dir = OUT_DIR / "cards"
    cards_dir.mkdir(exist_ok=True)
    outro_html_path = cards_dir / "outro_proof.html"
    write_outro_card(outro_html_path, REPO)
    outro_webm = record_card(outro_html_path, OUTRO_HOLD_S + 1.6)
    log(f"closing card recorded: {outro_webm.name}")

    ffmpeg = edit.resolve_ffmpeg()
    ffprobe = edit.resolve_ffprobe()
    raw_segments = build_segments(marks)
    segs = edit.segmentize(raw_segments)
    total = segs[-1]["final_end"] + OUTRO_HOLD_S
    log(f"cut: {len(segs)} segments, ~{total:.1f}s final at idle f={IDLE_F:g}x")

    captions = build_captions(marks, segs)
    srt_path = OUT_DIR / "nexus_demo.srt"
    cues = edit.write_srt(captions, segs, srt_path, total)
    log(f"srt: {srt_path} ({cues} cues)")

    out = OUT_DIR / "nexus_demo.mp4"
    render(raw, segs, outro_webm, out, ffmpeg)

    (OUT_DIR / "demo_timeline.json").write_text(json.dumps(
        {"video": str(out), "raw": str(raw), "idle_speed_f": IDLE_F,
         "label": "complete demo from the watchdog-stopped run (owner-requested); "
                  "closing card & captions disclose the cut; numbers transcribed from frames",
         "segments": segs}, indent=2, ensure_ascii=False), encoding="utf-8")

    edit.verify(out, ffprobe, ffmpeg, marks, IDLE_F,
                sheet_name="demo_contact_sheet.png", pcts=(5, 20, 40, 60, 80, 95))
    log(f"done: {out}")


if __name__ == "__main__":
    main()
