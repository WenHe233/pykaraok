"""pykaraok command line.  Every command accepts --json for machine-readable output."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__


def _out(args, data: dict, text: str | None = None) -> None:
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write((text if text is not None else json.dumps(data, ensure_ascii=False, indent=2)) + "\n")


def _framerate(args):
    from .aegi.vfr import Framerate
    if getattr(args, "fps", None):
        s = args.fps
        if "/" in s:
            n, d = s.split("/", 1)
            return Framerate.cfr(int(n), int(d))
        return Framerate.from_fps(float(s))
    if getattr(args, "video", None):
        from .render import probe
        info = probe.video_info(args.video)
        return Framerate.cfr(*info["fps"])
    return None


def _run_options(args):
    from .aegi.runtime import RunOptions
    video_size = None
    if getattr(args, "video", None):
        from .render import probe
        info = probe.video_info(args.video)
        video_size = (info["width"], info["height"])
    dialog = None
    if getattr(args, "dialog", None):
        dialog = json.loads(Path(args.dialog).read_text(encoding="utf-8")) if os.path.exists(args.dialog) \
            else json.loads(args.dialog)
    from .cli_more import default_fonts
    fonts = default_fonts(Path(args.input), args.fonts) if getattr(args, "input", None) else         __import__("pykaraok.fonts", fromlist=["resolve"]).resolve(args.fonts)
    return RunOptions(
        include_dirs=args.include or [],
        font_dirs=fonts,
        metrics=args.metrics,
        trace_level=args.trace,
        video_size=video_size,
        framerate=_framerate(args),
        seed=args.seed,
        dialog=dialog,
        echo_logs=args.echo,
    )


def _add_run_args(p):
    p.add_argument("--fonts", action="append", help="font dir, font file or zip font pack (repeatable; default: "
                                                    "fonts next to the input file); loaded privately for measuring")
    p.add_argument("--include", action="append", help="extra Lua include dir (repeatable)")
    p.add_argument("--metrics", default="auto", choices=["auto", "gdi", "fonttools"],
                   help="text_extents backend (auto = GDI on Windows, like Aegisub)")
    p.add_argument("--video", help="video file: enables aegisub.video_size and frame_from_ms like a loaded video")
    p.add_argument("--fps", help="frame rate for frame_from_ms, e.g. 24000/1001 (overrides --video)")
    p.add_argument("--seed", type=int, help="math.randomseed value before the script runs")
    p.add_argument("--trace", type=int, default=3, help="aegisub.debug.out level filter (default 3)")
    p.add_argument("--dialog", help="JSON (or a path to JSON) answering aegisub.dialog.display: "
                                    '{"button": "OK", "values": {...}}')
    p.add_argument("--echo", action="store_true", help="print script log output while running")


# ---------------------------------------------------------------- commands

def cmd_apply(args) -> int:
    from .aegi.templater import apply_file
    dst = args.output or args.input
    if not args.output and not args.in_place:
        print("refusing to overwrite the input: pass -o OUTPUT or --in-place", file=sys.stderr)
        return 2
    res = apply_file(args.input, dst, args.engine, _run_options(args), keep_furigana_styles=args.keep_furigana_styles)
    data = res.to_dict()
    lines = [f"{res.status}: {res.stats.get('fx_lines', 0)} fx lines -> {dst}" if res.ok else f"{res.status}: {res.message}"]
    if res.can_template is False:
        lines.append("note: Aegisub would disable 'Apply karaoke template' (no template in the first 50 dialogue lines)")
    for w in res.warnings:
        lines.append("warning: " + w)
    for lv, m in res.logs:
        lines.append(f"[log {lv}] {m.rstrip()}")
    _out(args, data, "\n".join(lines))
    return 0 if res.ok else 1


def cmd_run_macro(args) -> int:
    from .aegi.runtime import AegiRuntime
    from .ass.document import AssDocument
    doc = AssDocument.load(args.input)
    rt = AegiRuntime(doc, _run_options(args), script_path=doc.path)
    rt.load_script(args.script)
    if args.list:
        _out(args, {"macros": rt.macro_names()}, "\n".join(rt.macro_names()))
        return 0
    name = args.macro or (rt.macro_names()[0] if rt.macro_names() else None)
    if not name:
        print("the script registers no macros", file=sys.stderr)
        return 2
    if not args.output:
        print("pass -o OUTPUT (the input is never overwritten)", file=sys.stderr)
        return 2
    sel = [int(x) for x in args.selected.split(",")] if args.selected else None
    status, msg, secs = rt.run_macro(name, sel, args.active or 0)
    if status == "ok":
        rt.commit_to(doc)
        doc.save(args.output)
    data = {"status": status, "message": msg, "seconds": round(secs, 3),
            "logs": [{"level": lv, "message": m} for lv, m in rt.logs]}
    _out(args, data, f"{status} {msg}".strip())
    return 0 if status == "ok" else 1


def cmd_diff(args) -> int:
    from .ass.document import AssDocument
    from .qa.compare import compare_docs
    rep = compare_docs(AssDocument.load(args.a), AssDocument.load(args.b),
                       effect=None if args.all else args.effect, max_examples=args.examples)
    d = rep.to_dict()
    text = json.dumps({k: v for k, v in d.items() if k != "examples"}, ensure_ascii=False)
    for e in d["examples"]:
        text += "\n- " + e["a"][:300] + "\n+ " + e["b"][:300]
    _out(args, d, text)
    return 0 if rep.only_benign else 1


def cmd_doctor(args) -> int:
    from . import config
    from .aegi import moon
    info = {"pykaraok": __version__, "python": sys.version.split()[0], "platform": sys.platform}
    try:
        import lupa
        from lupa import luajit21
        info["lupa"] = lupa.__version__
        info["luajit"] = luajit21.LuaRuntime().eval("jit and jit.version")
    except Exception as exc:  # pragma: no cover
        info["lupa"] = f"ERROR {exc}"
    for mod in ("fontTools", "numpy", "PIL", "shapely", "pathops", "opencc"):
        try:
            m = __import__(mod)
            info[mod] = getattr(m, "__version__", "ok")
        except Exception:
            info[mod] = None
    info["ffmpeg"] = config.find_tool("ffmpeg", "PYKARAOK_FFMPEG")
    info["ffprobe"] = config.find_tool("ffprobe", "PYKARAOK_FFPROBE")
    info["moonc"] = moon.find_moonc()
    info["cache_dir"] = str(config.cache_dir())
    info["include_dirs"] = [str(p) for p in config.default_include_dirs()]
    info["aegisub_installs"] = [str(p) for p in config.known_aegisub_automation_dirs()]
    try:
        from .aegi import x0539
        info["0x539"] = x0539.status()
    except Exception as exc:
        info["0x539"] = f"unavailable: {exc}"
    try:
        from . import libs
        info["libraries"] = libs.status()
    except Exception as exc:
        info["libraries"] = f"unavailable: {exc}"
    missing = [k for k in ("ffmpeg", "ffprobe") if not info[k]]
    text = "\n".join(f"{k}: {v}" for k, v in info.items())
    if missing:
        text += "\nmissing: " + ", ".join(missing)
    _out(args, info, text)
    return 0


def cmd_setup(args) -> int:
    from .aegi import moon
    what = args.what
    result = {}
    if what in ("moonc", "all"):
        result["moonc"] = moon.find_moonc() or moon.download_moonc(log=lambda m: print(m, file=sys.stderr))
    if what in ("0x539", "all"):
        from .aegi import x0539
        result["0x539"] = x0539.setup(ref=args.ref, log=lambda m: print(m, file=sys.stderr))
    if what in ("libs", "all"):
        from . import libs
        result["libs"] = libs.setup(source=args.source, log=lambda m: print(m, file=sys.stderr))
    _out(args, result)
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="pykaraok", description="Headless Aegisub karaoke templaters, rendering and QA")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--json", action="store_true", help="machine-readable output")
        return p

    p = common(sub.add_parser("apply", help="apply karaoke templates (Aegisub: Apply karaoke template)"))
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--engine", default="stock", choices=["stock", "0x539"])
    p.add_argument("--keep-furigana-styles", action="store_true",
                   help="keep the unused <style>-furigana styles karaskel generates (Aegisub keeps them)")
    _add_run_args(p)
    p.set_defaults(fn=cmd_apply)

    p = common(sub.add_parser("run-macro", help="run any Automation 4 Lua/Moon macro headlessly"))
    p.add_argument("script")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=False)
    p.add_argument("--macro", help="macro name (default: the first registered)")
    p.add_argument("--list", action="store_true", help="list registered macros and exit")
    p.add_argument("--selected", help="comma separated 1-based line indices passed as the selection")
    p.add_argument("--active", type=int)
    _add_run_args(p)
    p.set_defaults(fn=cmd_run_macro)

    p = common(sub.add_parser("diff", help="compare the events of two files (classifies rounding-only changes)"))
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--effect", default="fx", help="only lines with this Effect (default fx)")
    p.add_argument("--all", action="store_true", help="compare all events")
    p.add_argument("--examples", type=int, default=5)
    p.set_defaults(fn=cmd_diff)

    p = common(sub.add_parser("doctor", help="check dependencies and installed extras"))
    p.set_defaults(fn=cmd_doctor)

    p = common(sub.add_parser("setup", help="download/compile optional components"))
    p.add_argument("what", choices=["moonc", "0x539", "libs", "all"])
    p.add_argument("--ref", default=None, help="git ref of The0x539/Aegisub-Scripts to use")
    p.add_argument("--source", default=None, help="local automation/include dir to take libraries from")
    p.set_defaults(fn=cmd_setup)

    from . import cli_more
    cli_more.register(sub, common, _add_run_args, _out, _run_options)

    args = ap.parse_args(argv)
    if os.environ.get("PYKARAOK_DEBUG"):
        return args.fn(args)
    try:
        return args.fn(args)
    except (RuntimeError, FileNotFoundError, KeyError, ValueError, SyntaxError) as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        if getattr(args, "json", False):
            sys.stdout.write(json.dumps({"error": msg, "type": exc.__class__.__name__}, ensure_ascii=False) + "\n")
        else:
            sys.stderr.write(f"error: {msg}\n(set PYKARAOK_DEBUG=1 for a traceback)\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
