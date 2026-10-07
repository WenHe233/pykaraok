"""build / extract / fxlib commands."""
from __future__ import annotations

import json
from pathlib import Path


def register(sub, common, add_run_args, out, run_options):
    p = common(sub.add_parser("build", help="template source + lyrics file -> single effect .ass (applied)"))
    p.add_argument("source", help="template source file (see `pykaraok help-source`)")
    p.add_argument("--lyrics", required=True, help="the user's lyrics .ass (not modified)")
    p.add_argument("-o", "--output", help="default: <lyrics>_特效.ass next to the lyrics file")
    p.add_argument("--engine", choices=["stock", "0x539"], help="default: --@meta engine=, else stock")
    p.add_argument("--styles", help="comma separated lyric styles (default: styles named by the templates)")
    p.add_argument("--k", dest="k_mode", default="keep", choices=["keep", "line", "char"],
                   help="lines without \\k: keep as is, one syllable for the whole line, or even per character")
    p.add_argument("--no-apply", action="store_true", help="only assemble, do not run the templater")
    p.add_argument("--strip-comments", action="store_true", help="drop Lua comments from code lines")
    p.add_argument("--input", dest="input", help=argparse_hidden())
    add_run_args(p)
    p.set_defaults(fn=lambda a: cmd_build(a, out, run_options))

    p = common(sub.add_parser("extract", help="write the template/code lines of an .ass as a template source file"))
    p.add_argument("ass")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(fn=lambda a: cmd_extract(a, out))

    p = common(sub.add_parser("fxlib", help="list the bundled Lua effect modules (for --@use)"))
    p.add_argument("module", nargs="?", help="print one module")
    p.set_defaults(fn=lambda a: cmd_fxlib(a, out))

    _register_tools(sub, common, out)


def argparse_hidden():
    import argparse
    return argparse.SUPPRESS


def cmd_build(args, out, run_options):
    from .build.project import build
    args.input = args.lyrics           # fonts default to the lyrics folder
    opts = None if args.no_apply else run_options(args)
    res = build(args.source, args.lyrics, args.output, args.engine,
                args.styles.split(",") if args.styles else None, args.k_mode,
                apply=not args.no_apply, run_options=opts, keep_comments=not args.strip_comments)
    d = res.to_dict()
    lines = [f"output: {res.output}", f"engine: {res.engine}", f"lyric lines: {res.lyric_lines} ({', '.join(res.lyric_styles)})",
             f"generated lines: {res.generated_lines}, first template at event #{res.first_template_event}"]
    for w in res.warnings:
        lines.append("warning: " + w)
    if res.apply:
        a = res.apply
        lines.append(f"apply: {a['status']} {a['message'][:2000]}".rstrip())
        if a.get("stats"):
            lines.append(f"fx lines: {a['stats'].get('fx_lines')}")
        for w in a.get("warnings", []):
            lines.append("warning: " + w)
        for lg in a.get("logs", [])[:20]:
            lines.append(f"[log {lg['level']}] {lg['message'].rstrip()}")
    out(args, d, "\n".join(lines))
    return 0 if (res.apply is None or res.apply["status"] == "ok") else 1


def cmd_extract(args, out):
    from .ass.document import AssDocument
    from .build.source import extract_from_events
    doc = AssDocument.load(args.ass)
    from .ass.document import format_style
    text = extract_from_events(doc.events, styles_raw={s["name"]: s.get("raw") or format_style(s) for s in doc.styles})
    Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    n = text.count("\n--@")
    out(args, {"output": args.output, "blocks": n}, f"{args.output}: {n} blocks")
    return 0


def cmd_fxlib(args, out):
    from . import config
    from .build.source import load
    mods = {}
    for p in sorted(config.FXLIB_DIR.glob("*.lua")):
        s = load(p)
        first = p.read_text(encoding="utf-8").splitlines()
        desc = next((ln[2:].strip() for ln in first if ln.startswith("--") and not ln.startswith("--@")), "")
        mods[p.stem] = {"description": desc, "blocks": [b.actor or b.effect for b in s.blocks]}
    if args.module:
        p = config.FXLIB_DIR / f"{args.module}.lua"
        text = p.read_text(encoding="utf-8")
        out(args, {"module": args.module, "source": text}, text)
        return 0
    text = "\n".join(f"{k}: {v['description']}" for k, v in mods.items())
    out(args, mods, text)
    return 0


def _register_tools(sub, common, out):
    from . import cli_tools
    cli_tools.register(sub, common, out)
