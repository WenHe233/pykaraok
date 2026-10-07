"""cht / draw / beats commands."""
from __future__ import annotations

import json
from pathlib import Path


def register(sub, common, out):
    p = common(sub.add_parser("cht", help="convert the Chinese lines of chosen styles to Traditional Chinese"))
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True, help="new file (the input is never overwritten)")
    p.add_argument("--styles", required=True, help="comma separated styles to convert")
    p.add_argument("--mode", default="s2twp", help="OpenCC config: s2twp (Taiwan, phrases), s2t, s2hk ...")
    p.add_argument("--rule", action="append", default=[], help="extra replacement after conversion, e.g. 你=妳")
    p.add_argument("--fonts", action="append", help="check glyph coverage of the converted lines with these fonts")
    p.set_defaults(fn=lambda a: cmd_cht(a, out))

    dp = sub.add_parser("draw", help="glyph outlines as ASS drawings")
    dsub = dp.add_subparsers(dest="what", required=True)
    p = common(dsub.add_parser("text", help="text -> \\p drawing (origin: top-left of the text cell)"))
    p.add_argument("text")
    p.add_argument("--font", required=True, help="family name or font file")
    p.add_argument("--size", type=float, required=True, help="font size as in the style")
    p.add_argument("--fonts", action="append")
    p.add_argument("--bold", action="store_true")
    p.add_argument("--italic", action="store_true")
    p.add_argument("--spacing", type=float, default=0.0)
    p.add_argument("--scale", type=float, default=1.0, help="multiply coordinates (8 for \\p4)")
    p.set_defaults(fn=lambda a: cmd_draw_text(a, out))
    p = common(dsub.add_parser("compose", help="build a missing character from parts of glyphs"))
    p.add_argument("--font", required=True)
    p.add_argument("--size", type=float, required=True)
    p.add_argument("--fonts", action="append")
    p.add_argument("--part", action="append", required=True,
                   help="CHAR[@x0,y0,x1,y1][+dx,dy][*sx,sy] (fractions of the cell), e.g. 气 or 汽@0.4,0,1,1+-0.3,0")
    p.set_defaults(fn=lambda a: cmd_draw_compose(a, out))

    p = common(sub.add_parser("beats", help="beat grid (BPM and first beat) of a song range"))
    p.add_argument("media", help="video or audio file")
    p.add_argument("--from", dest="start", required=True)
    p.add_argument("--to", dest="end", required=True)
    p.add_argument("--min", type=float, default=60)
    p.add_argument("--max", type=float, default=200)
    p.set_defaults(fn=lambda a: cmd_beats(a, out))


def cmd_cht(args, out):
    from .ass.document import AssDocument
    from .text.cht import convert_doc
    src, dst = Path(args.input), Path(args.output)
    if src.resolve() == dst.resolve():
        raise SystemExit("write the traditional version to a new file")
    rules = []
    for r in args.rule:
        a, _, b = r.partition("=")
        rules.append((a, b))
    doc = AssDocument.load(src)
    rep = convert_doc(doc, args.styles.split(","), args.mode, rules)
    doc.save(dst)
    data = rep.to_dict()
    data["output"] = str(dst)
    if args.fonts or True:
        from .cli_more import default_fonts
        from .qa.check import check_fonts
        conv = AssDocument.load(dst)
        conv.events = [e for e in conv.events if e["style"] in args.styles.split(",")]
        data["fonts"] = check_fonts(conv, default_fonts(src, args.fonts))
    lines = [f"{dst}: {rep.changed}/{rep.lines} lines changed ({rep.engine})"]
    for s in rep.samples[:3]:
        lines.append(f"  {s['before'][:60]}\n  -> {s['after'][:60]}")
    for lc in rep.length_changed:
        lines.append(f"warning: event {lc['event']} changed length: {lc['before']} -> {lc['after']} "
                     "(per-character \\k timing would shift)")
    for f in data.get("fonts", []):
        if f["level"] == "error":
            lines.append("error: " + f["message"])
    out(args, data, "\n".join(lines))
    return 0


def cmd_draw_text(args, out):
    from .draw.glyphs import resolve_face, text_drawing
    from .fonts import resolve
    face = resolve_face(args.font, resolve(args.fonts), args.bold, args.italic)
    drawing, width = text_drawing(face, args.text, args.size, args.spacing, args.scale)
    out(args, {"drawing": drawing, "width": round(width, 3), "font": face.family, "file": str(face.path)}, drawing)
    return 0


def _parse_part(spec: str):
    from .draw.compose import Part
    import re
    m = re.match(r"^(.)(?:@([\d.,\-]+))?(?:\+([\d.,\-]+))?(?:\*([\d.,\-]+))?$", spec)
    if not m:
        raise SystemExit(f"bad --part {spec!r}")
    ch, reg, mv, sc = m.groups()
    p = Part(ch)
    if reg:
        p.region = tuple(float(v) for v in reg.split(","))
    if mv:
        p.dx, p.dy = (float(v) for v in mv.split(","))
    if sc:
        p.sx, p.sy = (float(v) for v in sc.split(","))
    return p


def cmd_draw_compose(args, out):
    from .draw.compose import compose, path_to_ass
    from .draw.glyphs import resolve_face
    from .fonts import resolve
    face = resolve_face(args.font, resolve(args.fonts))
    path, adv = compose(face, [_parse_part(s) for s in args.part], args.size)
    d = path_to_ass(path)
    out(args, {"drawing": d, "advance": round(adv, 3), "font": face.family}, d)
    return 0


def cmd_beats(args, out):
    from .audio.beats import estimate
    from .cli_more import parse_time
    r = estimate(args.media, parse_time(args.start), parse_time(args.end), args.min, args.max)
    out(args, r, json.dumps(r, ensure_ascii=False))
    return 0
