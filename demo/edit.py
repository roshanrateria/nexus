"""D4: cut the raw recording into the final demo video.

Input : demo/out/raw/<name>.webm + demo/out/marks.json (from record_demo.py)
Output: demo/out/nexus_demo.mp4 (+ demo/out/nexus_demo.srt, timeline.json,
        and optional demo/out/x_clip.mp4)

Cut rules (everything comes from marks.json — no hardcoded times):
  * intro card, composer typing, the last KEEP seconds of the dashboard and
    the outro card play at 1x;
  * inside the monitored run region every marked idle interval plays at
    speed f; the live state-change moments around them stay at 1x;
  * f starts at --f (6) and grows until the total is <= --max-final (175 s;
    the spec ceiling is a 180 s video). If f would exceed 16, exit non-zero
    with "pick a faster goal".

Captions live ONLY in demo/out/nexus_demo.srt (per the demo owner's current
preference): every marks.json caption beat is mapped through the raw->final
timeline, padded to a readable minimum and cut so subtitles never overlap.
Pass --overlay-captions to record_demo.py to burn live pills instead.

ffmpeg filter chain per segment:
  [0:v]trim=start=a:end=b,setpts=(PTS-STARTPTS)/speed[vN]
then concat, fps=30, scale=1920:1080:flags=lanczos, libx264 crf18 preset
medium yuv420p +faststart.

Also:
  --voiceover path.wav  muxes afterwards (-c:a aac -shortest)
  --x-clip              additional <=30s teaser (first plan / first verified
                        evidence / report + evidence sheet)
  --verify-only         D6 checks against an existing mp4, no render
Exit 0 iff render + verification passed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
OUT_DIR = DEMO_DIR / "out"
RAW_DIR = OUT_DIR / "raw"
KEEP_1X_S = 25.0            # last seconds of the dashboard kept at 1x
TYPE_TAIL_S = 2.5           # 1x cushion after the Start click
MIN_FINAL = 175.0           # target ceiling before the 180s check
MAX_F = 16.0
MIN_F = 3.0

FFMPEG = None


def log(msg: str) -> None:
    print(f"[edit] {msg}", flush=True)


def resolve_ffmpeg() -> str:
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("[edit] no ffmpeg on PATH and imageio-ffmpeg is not installed "
                 "(pip install -r demo/requirements-demo.txt)")


def resolve_ffprobe() -> str:
    import shutil
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    sys.exit("[edit] ffprobe not found on PATH (install ffmpeg/ffprobe for verification)")


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
         "-show_entries", "format=duration,size",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    return {
        "codec": stream.get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": float(fmt.get("duration") or 0.0),
        "size": int(fmt.get("size") or 0),
    }


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------- timeline

def build_timeline(marks: dict, f: float, keep_s: float, type_tail: float) -> list[tuple]:
    """Segments = (start_raw, end_raw, speed, label) in RAW seconds; the live
    beats and timings all come from marks.json (scenes, idle intervals)."""
    scenes = marks["scenes"]
    intro = scenes["intro"]                     # [a, b]
    dashboard_start = float(scenes["dashboard"][0])
    start_click = float(scenes["start_click"])
    outro = scenes["outro"]                     # [a, b]
    dashboard_end = float(outro[0])             # dashboard scenes stop here

    prerun_end = clamp(start_click + type_tail, dashboard_start, dashboard_end)
    keep_start = clamp(dashboard_end - keep_s, prerun_end, dashboard_end)

    raw_segments: list[tuple[float, float, float, str]] = [
        (0.0, intro[1], 1.0, "intro card"),
        (dashboard_start, prerun_end, 1.0, "composer typing -> start"),
    ]

    # monitored run region: idle stretches at f, everything else at 1x
    idles = []
    for interval in marks.get("idle_intervals", []):
        a = float(interval["start"])
        b = float(interval.get("end") or 0.0)
        if b <= a:
            continue
        a = clamp(a, prerun_end, keep_start)
        b = clamp(b, prerun_end, keep_start)
        if b - a >= 2.0:  # ignore slivers; a 2s+ idle only becomes a segment
            idles.append((a, b))
    idles.sort()
    cursor = prerun_end
    for a, b in idles:
        if a <= cursor:
            cursor = max(cursor, b)
            continue
        raw_segments.append((cursor, a, 1.0, "live run"))
        raw_segments.append((a, b, f, "time-lapse idle"))
        cursor = b
    if cursor < keep_start:
        raw_segments.append((cursor, keep_start, 1.0, "live run"))
    raw_segments.append((keep_start, dashboard_end, 1.0, "finale: report + evidence"))
    raw_segments.append((outro[0], outro[1], 1.0, "outro card"))
    return fold_same_speed(raw_segments)


def fold_same_speed(raw_segments: list[tuple]) -> list[tuple]:
    """Merges adjacent segments with the same speed (no split between live
    beats that had nothing between them), dropping zero-length pieces."""
    folded: list[tuple] = []
    for a, b, speed, label in raw_segments:
        if b - a < 0.05:
            continue
        if folded and folded[-1][2] == speed and abs(a - folded[-1][1]) < 0.05:
            folded[-1] = (folded[-1][0], b, speed, folded[-1][3])
        else:
            folded.append((a, b, speed, label))
    return folded


def segmentize(raw_segments) -> list[dict]:
    segs: list[dict] = []
    final_t = 0.0
    for a, b, speed, label in raw_segments:
        span = b - a
        if span <= 0:
            continue
        segs.append({
            "raw_start": round(a, 3),
            "raw_end": round(b, 3),
            "speed": speed,
            "label": label,
            "final_start": round(final_t, 3),
        })
        final_t += span / speed
        segs[-1]["final_end"] = round(final_t, 3)
    return segs


def map_time(segs: list[dict], raw_t: float) -> float:
    """piecewise raw -> final."""
    for seg in segs:
        if seg["raw_start"] <= raw_t <= seg["raw_end"]:
            delta = (max(raw_t, seg["raw_start"]) - seg["raw_start"]) / seg["speed"]
            return seg["final_start"] + delta
    return segs[-1]["final_end"]


def srt_time(seconds: float) -> str:
    ms_total = round(clamp(seconds, 0.0, 3.5e6) * 1000)
    h, rest = divmod(ms_total, 3600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(captions: list[dict], segs: list[dict], path: Path, final_duration: float) -> int:
    """Captions, mapped into final time: minimum 2.2 s on screen, clipped so
    subtitles never overlap, ordering by their real beat time."""
    slots = sorted(
        (
            {"text": c["text"], "a": map_time(segs, float(c["t_start"])),
             "b": map_time(segs, float(c["t_end"]))}
            for c in captions
        ),
        key=lambda c: c["a"],
    )
    minimum = 2.2
    rows = []
    prev_end = 0.0
    for slot in slots:
        a = max(slot["a"], prev_end + 0.12)
        b = max(slot["b"], a + minimum)
        b = min(b, final_duration - 0.4, a + 8.0)
        if b - a < 0.8 or a >= final_duration:
            continue
        rows.append((a, b, slot["text"]))
        prev_end = b
    text = "".join(
        f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t.strip()}\n\n"
        for i, (a, b, t) in enumerate(sorted(rows, key=lambda r: r[0]), 1)
    )
    path.write_text(text, encoding="utf-8-sig")
    return len(rows)


# ------------------------------------------------------------------ render

def render_raw(raw: Path, segs: list[dict], out: Path, ffmpeg: str) -> None:
    parts = []
    inputs = []
    for i, seg in enumerate(segs):
        parts.append(
            f"[0:v]trim=start={seg['raw_start']:.3f}:end={seg['raw_end']:.3f},"
            f"setpts=(PTS-STARTPTS)/{seg['speed']}[v{i}]"
        )
        inputs.append(f"[v{i}]")
    graph = (
        ";".join(parts)
        + f";{''.join(inputs)}concat=n={len(segs)}:v=1:a=0[vc];"
        + "[vc]fps=30,scale=1920:1080:flags=lanczos,format=yuv420p[vout]"
    )
    command = [
        ffmpeg, "-y", "-i", str(raw),
        "-filter_complex", graph,
        "-map", "[vout]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ]
    log("ffmpeg render start")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-3000:] + "\n")
        sys.exit(f"[edit] ffmpeg failed (rc={result.returncode})")
    log("ffmpeg render done")


def mux_voiceover(out: Path, voiceover: Path, ffmpeg: str) -> None:
    tmp = out.with_suffix(".audio.mp4")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(out), "-i", str(voiceover),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "160k", "-shortest", str(tmp)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-2000:] + "\n")
        sys.exit("[edit] voiceover mux failed")
    tmp.replace(out)


def render_xclip(raw: Path, marks: dict, out: Path, ffmpeg: str, ceiling: float = 30.0) -> None:
    """Teaser <= 30s: around the first plan, the first verified evidence and
    the report + evidence sheet finale."""
    def beat(text_prefix: str) -> float:
        for caption in marks.get("captions", []):
            if caption["text"].startswith(text_prefix):
                return float(caption["t_start"])
        return 0.0
    plan_t = beat("Planner")
    ev_t = beat("Every quote")
    sheet_t = float(marks.get("scenes", {}).get("evidence_sheet") or 0.0)
    dashboard_end = float(marks["scenes"]["outro"][0])
    pieces = [
        (max(0.0, plan_t - 2.0), plan_t + 8.0, "first plan"),
        (max(0.0, ev_t - 2.0), ev_t + 8.0, "first evidence"),
        (max(0.0, sheet_t - 1.0), min(dashboard_end, sheet_t + 10.0), "report + sheet"),
    ]
    pieces = [(a, b, name) for (a, b, name) in pieces if b > max(a, 0.05)]
    total = sum(b - a for a, b, _ in pieces)
    if total > ceiling:
        # shrink proportionally to honor the 30s ceiling
        scale = ceiling / total
        pieces = [(a, a + (b - a) * scale, name) for a, b, name in pieces]
    if not pieces:
        log("x-clip skipped: no beats found in marks")
        return
    for i in range(1, len(pieces)):
        if pieces[i][0] <= pieces[i - 1][1]:
            pieces[i] = (pieces[i - 1][1] + 0.05, max(pieces[i][1], pieces[i - 1][1] + 0.85), pieces[i][2])
    parts = []
    for i, (a, b, name) in enumerate(pieces):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)[x{i}]")
    graph = (
        ";".join(parts)
        + f";{''.join('[x%d]' % i for i in range(len(pieces)))}concat=n={len(pieces)}:v=1:a=0[xv];"
        + "[xv]fps=30,scale=1920:1080:flags=lanczos,format=yuv420p[xout]"
    )
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(raw), "-filter_complex", graph, "-map", "[xout]",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-2000:] + "\n")
        sys.exit("[edit] x-clip render failed")
    for a, b, name in pieces:
        log(f"x-clip segment {name}: {a:.1f}-{b:.1f}s")


# ------------------------------------------------------------ verification

def verify(final: Path, ffprobe: str, ffmpeg: str, marks: dict, f: float,
           sheet_name: str = "contact_sheet.png",
           pcts: tuple = (5, 20, 40, 60, 80, 95)) -> dict:
    info = probe(final, ffprobe)
    failures = []
    if not (0.0 < info["duration"] <= 180.0):
        failures.append(f"duration {info['duration']:.1f}s outside (0, 180]")
    if info["codec"] != "h264":
        failures.append(f"codec {info['codec']}")
    if (info["width"], info["height"]) != (1920, 1080):
        failures.append(f"size {info['width']}x{info['height']}")
    if failures:
        for item in failures:
            log(f"VERIFY FAIL: {item}")
        sys.exit(3)

    # 6 frames -> contact sheet
    frames = []
    contact_dir = OUT_DIR / "contact"
    contact_dir.mkdir(parents=True, exist_ok=True)
    for i, pct in enumerate(pcts):
        target = contact_dir / f"f{pct}.png"
        subprocess.run(
            [ffmpeg, "-y", "-ss", f"{info['duration'] * pct / 100.0:.3f}",
             "-i", str(final), "-frames:v", "1", str(target)],
            capture_output=True, check=True,
        )
        frames.append((pct, target))

    from PIL import Image, ImageDraw, ImageStat
    tile_w, tile_h = 640, 360
    sheet = Image.new("RGB", (tile_w * 2, tile_h * 3), "#05070c")
    draw = ImageDraw.Draw(sheet)
    stats = []
    row = 0
    for index, (pct, target) in enumerate(frames):
        img = Image.open(target).convert("RGB")
        std = ImageStat.Stat(img).stddev
        mean = ImageStat.Stat(img).mean
        stats.append((pct, round(sum(std) / 3, 1), round(sum(mean) / 3, 1)))
        if sum(std) / 3 <= 12:
            failures.append(f"frame {pct}% near-uniform (stddev {sum(std)/3:.1f})")
        if sum(mean) / 3 < 18:
            failures.append(f"frame {pct}% dark-flat (mean {sum(mean)/3:.1f})")
        col = index % 2
        row = index // 2
        sheet.paste(img.resize((tile_w, tile_h)), (col * tile_w, row * tile_h))
        draw.text((col * tile_w + 8, row * tile_h + 6), f"{pct}%  std={stats[-1][1]} mean={stats[-1][2]}", fill="#e6eaf0")
    sheet_path = OUT_DIR / sheet_name
    sheet.save(sheet_path)
    for f_path in (OUT_DIR / "contact").glob("*.png"):
        f_path.unlink()
    try:
        (OUT_DIR / "contact").rmdir()
    except OSError:
        pass

    final_state = marks.get("final") or {}
    print("\n=== demo summary ===")
    print(f"duration      : {info['duration']:.1f} s")
    print(f"size          : {info['size'] / 1e6:.1f} MB")
    print(f"resolution    : {info['width']}x{info['height']} {info['codec']}")
    print(f"idle speed    : {f}x")
    print(f"captions      : {len(marks.get('captions', []))} (srt sidecar)")
    if final_state:
        print(f"final status  : {final_state.get('status')}")
        print(f"mode          : {final_state.get('mode')}")
        print(f"planner calls : {final_state.get('planner_calls')}")
        print(f"steps         : {final_state.get('steps')}")
        print(f"cost_usd      : {final_state.get('cost_usd')}")
        print(f"evidences     : {final_state.get('evidences')}")
        print(f"sites         : {final_state.get('sites')}")
    print(f"contact sheet : {sheet_path}")
    if failures:
        for item in failures:
            log(f"VERIFY FAIL: {item}")
        sys.exit(4)
    return info


# --------------------------------------------------------------- proof cut

def range_with_idles(a: float, b: float, marks: dict, f: float) -> list[tuple]:
    """Covers raw range [a,b] at 1x except recorded idle stretches (in- and
    out-of-range clamped) which play at f — the same time-lapse rules the
    success demo uses, applied to an edit-time sub-window."""
    raw_idles = []
    for iv in marks.get("idle_intervals", []):
        s = float(iv.get("start") or 0.0)
        e = float(iv.get("end") or 0.0)
        e = e or b  # an interval still open at the watchdog cut closes here
        s = clamp(s, a, b)
        e = clamp(e, a, b)
        if e - s >= 0.8:
            raw_idles.append((s, e))
    raw_idles.sort()
    pieces: list[tuple] = []
    cursor = a
    for s, e in raw_idles:
        if s <= cursor:
            cursor = max(cursor, e)
            continue
        pieces.append((cursor, s, 1.0, "live"))
        pieces.append((s, e, f, "time-lapse"))
        cursor = e
    if cursor < b:
        pieces.append((cursor, b, 1.0, "live"))
    return pieces


def build_proof_timeline(marks: dict, f: float) -> list[tuple]:
    """Anchors come from the failed run's marks (caption beats, intro card,
    recording end); the +-second windows are editorial padding around those
    real beats. The reel never claims goal_achieved - it is an engine-proof
    cut of a watchdog-stopped run."""
    scenes = marks.get("scenes") or {}
    caps = marks.get("captions") or []
    intro_end = float((scenes.get("intro") or [0.0, 3.3])[1])
    rec_end = float(scenes.get("recording_end") or 0.0)

    def beat(prefix: str):
        for c in caps:
            if str(c.get("text") or "").startswith(prefix):
                return float(c["t_start"]), float(c["t_end"])
        return None, None

    ranges: list[tuple[float, float]] = [(0.0, intro_end)]
    p0, p1 = beat("Planner")
    if p0 is not None:
        ranges.append((p0 - 1.2, p1 + 10.6))      # plan split + mode caption
    q0, q1 = beat("Every quote")
    if q0 is not None:
        ranges.append((q0 - 7.0, q1 + 2.7))       # first verified quotes
    if rec_end:
        ranges.append((rec_end - 23.5, rec_end - 0.1))  # cap moment + ledger

    out: list[tuple] = []
    for a, b in ranges:
        if b - a < 0.5:
            continue
        out.extend(range_with_idles(a, b, marks, f))
    return fold_same_speed(out)


def proof_captions(marks: dict, segs: list[dict]) -> list[dict]:
    """Captions for the proof reel: run captions whose raw beat lands inside
    the kept windows, plus synthesised captions hand-transcribed from what
    the reel's own frames really show (no invented numbers)."""
    def inside(raw_t: float) -> bool:
        return any(s["raw_start"] <= raw_t <= s["raw_end"] for s in segs)

    kept = [c for c in marks.get("captions", []) if inside(float(c["t_start"]))]
    synth: list[dict] = []
    planner = next((c for c in marks.get("captions", []) if str(c.get("text") or "").startswith("Planner")), None)
    if planner and inside(float(planner["t_start"]) + 0.2):
        t0 = float(planner["t_start"]) + 0.2
        synth.append({"text": "Planner split the real goal into three source visits: SIA, a US .gov page, TSMC investor relations.",
                      "t_start": round(t0, 2), "t_end": round(t0 + 4.0, 2)})
    scenes = marks.get("scenes") or {}
    rec_end = float(scenes.get("recording_end") or 0.0)
    if rec_end:
        t0 = rec_end - 13.5
        synth.append({"text": "Watchdog, not the engine: cut mid-research at the demo's run cap - $0.22 billed, 4 verified quotes live in the ledger.",
                      "t_start": round(t0, 2), "t_end": round(t0 + 4.2, 2)})
    return sorted(kept + synth, key=lambda c: c["t_start"])


# -------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description="Cut the raw demo recording into the final MP4")
    parser.add_argument("--raw", default=None, help="raw webm (default: the video listed in marks.json)")
    parser.add_argument("--marks", default=str(OUT_DIR / "marks.json"))
    parser.add_argument("--out", default=str(OUT_DIR / "nexus_demo.mp4"))
    parser.add_argument("--f", type=float, default=6.0, help="initial idle speed factor (3..16)")
    parser.add_argument("--max-final", type=float, default=MIN_FINAL)
    parser.add_argument("--keep", type=float, default=KEEP_1X_S, help="seconds of the dashboard tail at 1x")
    parser.add_argument("--voiceover", default=None, help="path to wav; muxed with -c:a aac -shortest")
    parser.add_argument("--x-clip", action="store_true", help="also build demo/out/x_clip.mp4 (<= 30s)")
    parser.add_argument("--proof-cut", action="store_true",
                        help="engine-proof reel from a watchdog-stopped run: newest"
                        " demo/out/marks_failed_a*.json + its raw webm -> proof_cut.mp4"
                        " (never claims goal_achieved, never replaces nexus_demo.mp4)")
    parser.add_argument("--verify-only", action="store_true", help="D6 checks on an existing mp4 only")
    args = parser.parse_args()

    ffmpeg = resolve_ffmpeg()
    ffprobe = resolve_ffprobe()
    marks_path = Path(args.marks)
    if not marks_path.is_file() and args.proof_cut:
        # newest failed attempt whose raw webm still exists (mtimes beat names)
        failed = sorted(OUT_DIR.glob("marks_failed_a*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        for cand in failed:
            cand_video = Path(json.loads(cand.read_text(encoding="utf-8")).get("video") or "")
            if cand_video.is_file():
                marks_path = cand
                log(f"proof cut: using {cand.name} ({cand_video.name})")
                break
        else:
            sys.exit("[edit] proof cut: no marks_failed_a*.json with an existing raw webm")
    if not marks_path.is_file():
        sys.exit(f"[edit] marks not found: {marks_path}")
    marks = json.loads(marks_path.read_text(encoding="utf-8"))
    raw = Path(args.raw or marks.get("video") or "")
    if not raw.is_file():
        candidates = sorted(RAW_DIR.glob("*.webm")) if RAW_DIR.is_dir() else []
        if not candidates:
            sys.exit("[edit] no raw webm found")
        raw = candidates[-1]
        log(f"no --raw given, using newest raw: {raw}")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.proof_cut:
        if args.voiceover or args.x_clip:
            sys.exit("[edit] --voiceover/--x-clip are for the success-demo cut only")
        if "goal_achieved" in json.dumps(marks.get("final") or {}):
            sys.exit("[edit] refuses to build a proof cut from a run that actually succeeded")
        proof_out = out_path if args.out != str(OUT_DIR / "nexus_demo.mp4") else OUT_DIR / "proof_cut.mp4"
        f = clamp(args.f, MIN_F, MAX_F)
        raw_segments = build_proof_timeline(marks, f)
        segs = segmentize(raw_segments)
        if not segs:
            sys.exit("[edit] proof cut: no usable beats in marks")
        log(f"proof cut: {len(segs)} segments, {segs[-1]['final_end']:.1f}s at idle f={f:g}x")
        render_raw(raw, segs, proof_out, ffmpeg)
        captions = proof_captions(marks, segs)
        srt_path = proof_out.with_suffix(".srt")
        subs = write_srt(captions, segs, srt_path, segs[-1]["final_end"])
        log(f"srt: {srt_path} ({subs} cues)")
        (OUT_DIR / "proof_timeline.json").write_text(json.dumps(
            {"video": str(proof_out), "raw": str(raw), "idle_speed_f": f,
             "label": "engine-proof reel of a watchdog-stopped run (no goal_achieved claim)",
             "segments": segs}, indent=2, ensure_ascii=False), encoding="utf-8")
        verify(proof_out, ffprobe, ffmpeg, marks, f,
               sheet_name="proof_contact_sheet.png", pcts=(10, 28, 50, 72, 88, 96))
        log(f"done: {proof_out}")
        return

    if args.verify_only:
        verify(out_path, ffprobe, ffmpeg, marks, args.f)
        return

    # find the smallest f (3..16) that fits the ceiling
    chosen = None
    f = float(args.f)
    while True:
        if f < MIN_F or f > MAX_F:
            break
        raw_segments = build_timeline(marks, f, args.keep, TYPE_TAIL_S)
        segs = segmentize(raw_segments)
        total = segs[-1]["final_end"] if segs else 0.0
        log(f"speed f={f:g}x -> {total:.1f}s over {len(segs)} segments")
        if total <= args.max_final:
            chosen = (f, segs)
            break
        f += 1.0
    if chosen is None:
        sys.exit("[edit] video is over the ceiling even at 16x — pick a faster goal")
    f, segs = chosen

    render_raw(raw, segs, out_path, ffmpeg)
    if args.voiceover:
        mux_voiceover(out_path, Path(args.voiceover), ffmpeg)

    # timeline.json: piecewise raw -> final
    timeline = {
        "video": str(out_path),
        "raw": str(raw),
        "idle_speed_f": f,
        "segments": segs,
        "anchors": [
            [seg["raw_start"], seg["final_start"]] for seg in segs
        ] + [[segs[-1]["raw_end"], segs[-1]["final_end"]]],
        "captions_final": [
            {"text": c["text"],
             "final_start": round(map_time(segs, float(c["t_start"])), 3),
             "final_end": round(map_time(segs, float(c["t_end"])), 3)}
            for c in sorted(marks.get("captions", []), key=lambda c: c["t_start"])
        ],
    }
    (OUT_DIR / "timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")

    srt_path = out_path.with_suffix(".srt")
    subs = write_srt(marks.get("captions", []), segs, srt_path, segs[-1]["final_end"])
    log(f"srt: {srt_path} ({subs} cues)")

    if args.x_clip:
        render_xclip(raw, marks, OUT_DIR / "x_clip.mp4", ffmpeg)

    verify(out_path, ffprobe, ffmpeg, marks, f)
    log(f"done: {out_path}")


if __name__ == "__main__":
    main()
