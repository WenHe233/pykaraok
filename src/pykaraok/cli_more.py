"""render / check / fonts commands."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_time(s: str) -> float:
    """'83.4', '1:23.4' or '0:01:23.40' -> seconds."""
    s = str(s).strip()
    parts = s.split(":")
    v = 0.0
    for p in parts:
        v = v * 60 + float(p)
    return v


def parse_rects(s: str | None):
    """'x,y,w,h' or 'x,y,w,h;x,y,w,h' -> rect or list of rects; 'auto'/'full' pass through."""
    if s is None or s in ("auto", "full"):
        return s
    rects = [tuple(int(float(v)) for v in r.split(",")) for r in s.split(";") if r.strip()]
    return rects[0] if len(rects) == 1 else rects


def default_fonts(ass_path: Path, given) -> list[Path]:
    """--fonts, else fonts and font-pack zips next to the .ass and next to its recorded video.

    Only the top level of those folders counts (fonts.font_files): font collections
    in subfolders are left alone.
    """
    from .fonts import font_files, resolve
    if given:
        return resolve(given)
    folders = [ass_path.resolve().parent]
    try:
        video = default_video(ass_path, None)
    except Exception:
        video = None
    if video is not None and video.resolve().parent not in folders:
        folders.append(video.resolve().parent)
    found = []
    for folder in folders:
        if font_files([folder]):
            found.append(folder)
        for z in folder.glob("*.zip"):
            name = z.name.lower()
            if "font" in name or "字体" in z.name:
                found.append(z)
    if not found:
        warn(f"no fonts next to {ass_path.name} or its video; pass --fonts (installed fonts are used otherwise)")
    return resolve(found)


def warn(msg: str) -> None:
    sys.stderr.write("warning: " + msg + "\n")


def default_video(ass_path: Path, given):
    if given:
        return Path(given)
    from .ass.document import AssDocument
    doc = AssDocument.load(ass_path)
    v = doc.project_property("Video File")
    if v and not v.startswith("?dummy"):
        p = Path(v)
        if not p.is_absolute():
            p = ass_path.resolve().parent / p
        if p.exists():
            return p
    return None


def _source(args, ass_path: Path):
    from .ass.document import AssDocument
    from .render.ffmpeg import Source
    video = None if getattr(args, "no_video", False) else default_video(ass_path, getattr(args, "video", None))
    if video is None and not getattr(args, "no_video", False):
        warn(f"no video for {ass_path.name} (none recorded or not found): drawing on a plain background "
             "at 23.976 fps; pass --video to use the real frames and frame rate")
    doc = AssDocument.load(ass_path)
    return Source.make(video, background=getattr(args, "bg", "gray"), doc=doc), video


def _range(args, ass_path: Path, pad: float = 1.0) -> tuple[float, float]:
    if getattr(args, "start", None) is not None and getattr(args, "end", None) is not None:
        return parse_time(args.start), parse_time(args.end)
    from .ass.document import AssDocument
    doc = AssDocument.load(ass_path)
    ev = [e for e in doc.events if e["effect"] == "fx" and not e["comment"]] or \
         [e for e in doc.events if e["effect"].lower() in ("karaoke", "kara")] or \
         [e for e in doc.events if not e["comment"]]
    if not ev:
        raise SystemExit("cannot determine a time range; pass --from and --to")
    t0 = min(e["start_time"] for e in ev) / 1000 - pad
    t1 = max(e["end_time"] for e in ev) / 1000 + pad
    if getattr(args, "start", None) is not None:
        t0 = parse_time(args.start)
    if getattr(args, "end", None) is not None:
        t1 = parse_time(args.end)
    return max(0.0, t0), t1


def _out_path(args, ass_path: Path, suffix: str) -> Path:
    if getattr(args, "output", None):
        return Path(args.output)
    return Path.cwd() / f"{ass_path.stem}_{suffix}"


def register(sub, common, add_run_args, out, run_options):
    from . import cli as _cli

    def add_render_common(p, with_range=False):
        p.add_argument("ass")
        p.add_argument("--video", help="video to draw on (default: the Video File recorded in the .ass)")
        p.add_argument("--no-video", action="store_true", help="draw on a plain background")
        p.add_argument("--bg", default="gray", help="background colour without video (gray, black, checker, #RRGGBB)")
        p.add_argument("--fonts", action="append", help="font dir (top level only), font file or zip font pack "
                                                        "(default: the .ass folder)")
        p.add_argument("-o", "--output")
        if with_range:
            p.add_argument("--from", dest="start")
            p.add_argument("--to", dest="end")

    rp = sub.add_parser("render", help="render frames, contact sheets and previews with libass")
    rsub = rp.add_subparsers(dest="what", required=True)

    p = common(rsub.add_parser("frame", help="one frame"))
    add_render_common(p)
    p.add_argument("--at", required=True, help="time, e.g. 1:23.45")
    p.add_argument("--width", type=int, default=960, help="output width (default 960; 0 = native)")
    p.add_argument("--crop", help="x,y,w,h (or several separated by ;) in video pixels")
    p.add_argument("--label", action="store_true", help="draw the timestamp")
    p.set_defaults(fn=lambda a: cmd_frame(a, out))

    p = common(rsub.add_parser("sheet", help="frames over a time range tiled into one image"))
    add_render_common(p, with_range=True)
    p.add_argument("--step", type=float, help="seconds between frames")
    p.add_argument("--fps", type=float, help="frames per second to sample (alternative to --step)")
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--width", type=int, default=480, help="tile width")
    p.add_argument("--crop", help="x,y,w,h (or several separated by ;)")
    p.set_defaults(fn=lambda a: cmd_sheet(a, out))

    p = common(rsub.add_parser("lines", help="each lyric line at entry, middle and exit (one row per line)"))
    add_render_common(p)
    p.add_argument("--styles", help="comma separated styles of the source lines")
    p.add_argument("--first", type=int, default=1, help="first line (1-based)")
    p.add_argument("--count", type=int, help="number of lines")
    p.add_argument("--per-sheet", type=int, default=8)
    p.add_argument("--phases", default="in,in+,mid,out-,out", help="subset of in,in+,mid,out-,out")
    p.add_argument("--crop", default="auto", help="auto (bands around the effect), full, or x,y,w,h[;...]")
    p.add_argument("--width", type=int, default=480, help="tile width")
    p.set_defaults(fn=lambda a: cmd_lines(a, out))

    p = common(rsub.add_parser("zoom", help="a region at native resolution, enlarged"))
    add_render_common(p)
    p.add_argument("--at", required=True)
    p.add_argument("--crop", required=True, help="x,y,w,h")
    p.add_argument("--scale", type=float, default=2.0)
    p.set_defaults(fn=lambda a: cmd_zoom(a, out))

    p = common(rsub.add_parser("preview", help="burn the subtitles into an mp4 of the song range"))
    add_render_common(p, with_range=True)
    p.add_argument("--bitrate", default="4500k")
    p.add_argument("--crf", type=int)
    p.add_argument("--width", type=int, help="scale the preview to this width")
    p.add_argument("--no-audio", action="store_true")
    p.set_defaults(fn=lambda a: cmd_preview(a, out))

    p = common(rsub.add_parser("vsf", help="one frame with VSFilter (CSRI, Windows) to spot VSFilter-only problems"))
    add_render_common(p)
    p.add_argument("--at", required=True)
    p.set_defaults(fn=lambda a: cmd_vsf(a, out))

    p = common(rsub.add_parser("perf", help="libass render cost per frame over a range"))
    add_render_common(p, with_range=True)
    p.set_defaults(fn=lambda a: cmd_perf(a, out))

    # ------------------------------------------------------------ check
    p = common(sub.add_parser("check", help="lint an effect file (Aegisub 50-line rule, libass collisions, fonts ...)"))
    p.add_argument("ass")
    p.add_argument("--fonts", action="append")
    p.add_argument("--reapply", action="store_true", help="re-apply the templates and require identical output")
    p.add_argument("--engine", default="stock", choices=["stock", "0x539"])
    p.add_argument("--video", help="video for render-based checks (default: the Video File recorded in the .ass)")
    p.add_argument("--no-video", action="store_true", help="render-based checks on a plain background")
    p.add_argument("--bg", default="gray", help="background colour without video")
    p.add_argument("--jumps", action="store_true", help="look for one-frame jumps (renders the range)")
    p.add_argument("--perf", action="store_true", help="measure libass cost per frame")
    p.add_argument("--original", help="original lyrics file: compare the static look line by line (--steady)")
    p.add_argument("--steady", action="store_true", help="with --original: pixel-compare at each line's middle")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    p.add_argument("--diff-dir", help="where to write steady-state diff images")
    p.add_argument("--strip-k", default="auto", choices=["auto", "yes", "no"],
                   help="--steady: compare against the original with \\k removed (fully sung); auto = when it has \\k")
    p.set_defaults(fn=lambda a: cmd_check(a, out))

    # ------------------------------------------------------------ fonts
    fp = sub.add_parser("fonts", help="font utilities")
    fsub = fp.add_subparsers(dest="what", required=True)
    p = common(fsub.add_parser("check", help="which fonts the file uses and whether every glyph exists"))
    p.add_argument("ass")
    p.add_argument("--fonts", action="append")
    p.set_defaults(fn=lambda a: cmd_fonts_check(a, out))
    p = common(fsub.add_parser("unpack", help="extract a zip font pack into the cache and print the directory"))
    p.add_argument("zip")
    p.set_defaults(fn=lambda a: out(a, {"dir": str(__import__("pykaraok.fonts", fromlist=["x"]).unpack_zip(Path(a.zip)))}))

    from . import cli_build
    cli_build.register(sub, common, add_run_args, out, run_options)


# ---------------------------------------------------------------- render commands

def cmd_frame(args, out):
    from .render import ffmpeg as rf
    ass = Path(args.ass)
    src, video = _source(args, ass)
    o = _out_path(args, ass, f"{parse_time(args.at):.2f}s.png".replace(".", "_", 1))
    rf.frame(ass, parse_time(args.at), o, src, default_fonts(ass, args.fonts), crop=parse_rects(args.crop),
             width=args.width or None, label=args.label)
    out(args, {"output": str(o), "video": str(video) if video else None}, str(o))
    return 0


def cmd_sheet(args, out):
    from .render import ffmpeg as rf
    ass = Path(args.ass)
    src, video = _source(args, ass)
    t0, t1 = _range(args, ass)
    o = _out_path(args, ass, "sheet.png")
    info = rf.sheet(ass, t0, t1, o, src, default_fonts(ass, args.fonts), step=args.step, fps=args.fps,
                    cols=args.cols, crop=parse_rects(args.crop), width=args.width)
    info["video"] = str(video) if video else None
    out(args, info, f"{o}  ({len(info['times'])} frames, {info['times'][0]}s .. {info['times'][-1]}s)")
    return 0


def cmd_lines(args, out):
    from .render import review
    ass = Path(args.ass)
    src, video = _source(args, ass)
    prefix = args.output or str(Path.cwd() / f"{ass.stem}_lines")
    if prefix.lower().endswith(".png"):
        prefix = prefix[:-4]
    res = review.line_sheets(ass, prefix, src, default_fonts(ass, args.fonts),
                             styles=args.styles.split(",") if args.styles else None,
                             phases=tuple(args.phases.split(",")), per_sheet=args.per_sheet,
                             crop=parse_rects(args.crop), width=args.width, first=args.first, count=args.count)
    text = "\n".join(f"{r['output']}: lines {r['lines'][0]['index']}-{r['lines'][-1]['index']}" for r in res)
    out(args, {"sheets": res, "video": str(video) if video else None}, text)
    return 0


def cmd_zoom(args, out):
    from .render import ffmpeg as rf
    ass = Path(args.ass)
    src, _ = _source(args, ass)
    rect = parse_rects(args.crop)
    o = _out_path(args, ass, "zoom.png")
    rf.frame(ass, parse_time(args.at), o, src, default_fonts(ass, args.fonts), crop=rect,
             width=int(rect[2] * args.scale))
    out(args, {"output": str(o)}, str(o))
    return 0


def cmd_preview(args, out):
    from .render import ffmpeg as rf
    ass = Path(args.ass)
    src, video = _source(args, ass)
    t0, t1 = _range(args, ass, pad=2.0)
    o = _out_path(args, ass, "preview.mp4")
    info = rf.preview(ass, o, t0, t1, src, default_fonts(ass, args.fonts), bitrate=args.bitrate,
                      width=args.width, audio=not args.no_audio, crf=args.crf)
    info["range"] = [round(t0, 3), round(t1, 3)]
    out(args, info, f"{o}  {info['bytes'] / 1e6:.1f} MB, {t0:.2f}s-{t1:.2f}s")
    return 0


def cmd_vsf(args, out):
    from .render import vsfilter
    ass = Path(args.ass)
    src, _ = _source(args, ass)
    o = _out_path(args, ass, "vsf.png")
    vsfilter.frame(ass, parse_time(args.at), o, src, default_fonts(ass, args.fonts))
    out(args, {"output": str(o), "dll": str(vsfilter.find_dll())}, str(o))
    return 0


def cmd_perf(args, out):
    from .render import ffmpeg as rf
    ass = Path(args.ass)
    src, _ = _source(args, ass)
    t0, t1 = _range(args, ass, pad=0)
    info = rf.render_time(ass, t0, t1, src, default_fonts(ass, args.fonts))
    out(args, info, json.dumps(info))
    return 0


# ---------------------------------------------------------------- check

def cmd_check(args, out):
    from .qa import check as qc
    ass = Path(args.ass)
    fonts = default_fonts(ass, args.fonts)
    opts = None
    if args.reapply:
        from .aegi.runtime import RunOptions
        opts = RunOptions(font_dirs=fonts)
    findings = qc.run_static(ass, fonts, reapply=args.reapply, options=opts, engine=args.engine)
    if args.jumps or args.perf or args.steady:
        from .qa import frames
        from .render import ffmpeg as rf
        src, video = _source(args, ass)
        t0, t1 = _range(args, ass, pad=0.5)
        if args.perf:
            info = rf.render_time(ass, t0, t1, src, fonts)
            level = "warn" if info["ms_per_frame"] > info["budget_ms_per_frame"] else "info"
            findings.append({"check": "perf", "level": level,
                             "message": f"libass needs {info['ms_per_frame']} ms per frame "
                                        f"(budget {info['budget_ms_per_frame']} ms)", **info})
        if args.jumps:
            info = frames.find_jumps(ass, t0, t1, src, fonts)
            level = "warn" if info["count"] else "info"
            findings.append({"check": "jumps", "level": level,
                             "message": f"{info['count']} one-frame jumps in {info['frames']} frames", **info})
        if args.steady:
            if not args.original:
                raise SystemExit("--steady needs --original")
            info = frames.steady_diff(args.original, ass, src, fonts, outdir=args.diff_dir, strip_k=args.strip_k)
            level = "warn" if info["changed"] else "info"
            how = " (original compared fully sung, \\k removed)" if info["stripped_k"] else ""
            findings.append({"check": "steady", "level": level,
                             "message": f"{info['changed']} of {info['lines']} time slots look different from the "
                                        f"original at their middle{how}", **info})
    errors = sum(1 for f in findings if f["level"] == "error")
    warns = sum(1 for f in findings if f["level"] == "warn")
    text = "\n".join(f"[{f['level']}] {f['check']}: {f['message']}" for f in findings)
    text += f"\n{errors} errors, {warns} warnings"
    out(args, {"findings": findings, "errors": errors, "warnings": warns}, text)
    return 1 if errors else 0


def cmd_fonts_check(args, out):
    from .qa import check as qc
    from .ass.document import AssDocument
    ass = Path(args.ass)
    findings = qc.check_fonts(AssDocument.load(ass), default_fonts(ass, args.fonts))
    text = "\n".join(f"[{f['level']}] {f['message']}" for f in findings)
    out(args, {"findings": findings}, text)
    return 1 if any(f["level"] == "error" for f in findings) else 0
