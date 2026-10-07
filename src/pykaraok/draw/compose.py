"""Compose a missing character from parts of other glyphs, and shapely -> ASS drawings.

A part is "take character C, keep the region R of its cell, move/scale it".
Regions and offsets are fractions of the cell (0..1, origin top-left), so a
spec does not depend on the font size:

    # 気 from 气 (keep everything) plus the inner part of 汽's right side ...
    compose(face, [Part("气"), Part("メ", region=(0.25, 0.45, 0.85, 0.95))], size=55)

Boolean operations run on the real curves (skia-pathops), so the result stays
smooth and overlapping parts are merged.
"""
from __future__ import annotations

from dataclasses import dataclass

import pathops

from ..metrics.fontdb import FontFace
from .glyphs import _metrics


@dataclass
class Part:
    char: str
    region: tuple[float, float, float, float] | None = None   # x0, y0, x1, y1 as cell fractions
    dx: float = 0.0          # move, cell fractions
    dy: float = 0.0
    sx: float = 1.0          # scale around the region's top-left
    sy: float = 1.0
    face: FontFace | None = None   # default: the target font


def _glyph_path(face: FontFace, ch: str, size: float) -> tuple[pathops.Path, float]:
    tt, asc, desc = _metrics(face)
    gname = (tt.getBestCmap() or {}).get(ord(ch))
    if gname is None:
        raise KeyError(f"{face.family} has no glyph for {ch!r}")
    k = size / (asc + desc)
    src = pathops.Path()
    tt.getGlyphSet()[gname].draw(src.getPen())
    # font units (y up, baseline 0) -> px (y down, cell top 0)
    out = pathops.Path()
    pen = out.getPen()
    for verb, pts in src.segments:
        tp = [(p[0] * k, (asc - p[1]) * k) for p in pts]
        if verb == "moveTo":
            pen.moveTo(tp[0])
        elif verb == "lineTo":
            pen.lineTo(tp[0])
        elif verb == "curveTo":
            pen.curveTo(*tp)
        elif verb == "qCurveTo":
            pen.qCurveTo(*tp)
        elif verb == "closePath":
            pen.closePath()
        elif verb == "endPath":
            pen.endPath()
    return out, tt["hmtx"][gname][0] * k


def _rect(x0, y0, x1, y1) -> pathops.Path:
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0, y0))
    pen.lineTo((x1, y0))
    pen.lineTo((x1, y1))
    pen.lineTo((x0, y1))
    pen.closePath()
    return p


def _transform(path: pathops.Path, fn) -> pathops.Path:
    out = pathops.Path()
    pen = out.getPen()
    for verb, pts in path.segments:
        tp = [fn(p) for p in pts]
        getattr(pen, verb)(*tp) if verb not in ("closePath", "endPath") else getattr(pen, verb)()
    return out


def compose(face: FontFace, parts: list[Part], size: float) -> tuple[pathops.Path, float]:
    """Returns the merged path (px, cell coordinates) and the advance of the first part's glyph."""
    result = None
    advance = None
    for part in parts:
        f = part.face or face
        path, adv = _glyph_path(f, part.char, size)
        if advance is None:
            advance = adv
        if part.region:
            x0, y0, x1, y1 = part.region
            path = pathops.op(path, _rect(x0 * size, y0 * size, x1 * size, y1 * size), pathops.PathOp.INTERSECTION)
            ox, oy = x0 * size, y0 * size
        else:
            ox, oy = 0.0, 0.0
        dx, dy = part.dx * size, part.dy * size
        path = _transform(path, lambda p, ox=ox, oy=oy, dx=dx, dy=dy, sx=part.sx, sy=part.sy:
                          (ox + (p[0] - ox) * sx + dx, oy + (p[1] - oy) * sy + dy))
        result = path if result is None else pathops.op(result, path, pathops.PathOp.UNION)
    if result is None:
        raise ValueError("no parts")
    result.simplify(fix_winding=True)
    return result, advance or size


def path_to_ass(path: pathops.Path, decimals: int = 2, scale: float = 1.0, ox: float = 0.0, oy: float = 0.0) -> str:
    def p(pt):
        fmt = f"%.{decimals}f"
        return (fmt % ((pt[0] + ox) * scale)).rstrip("0").rstrip(".") + " " + \
            (fmt % ((pt[1] + oy) * scale)).rstrip("0").rstrip(".")
    out = []
    cur = None
    for verb, pts in path.segments:
        if verb == "moveTo":
            out.append("m " + p(pts[0]))
            cur = pts[0]
        elif verb == "lineTo":
            out.append("l " + p(pts[0]))
            cur = pts[0]
        elif verb == "curveTo":
            out.append("b " + " ".join(p(q) for q in pts))
            cur = pts[-1]
        elif verb == "qCurveTo":
            # quadratic with implied on-curve points -> cubic segments
            pts = list(pts)
            on = cur
            for i in range(len(pts) - 1):
                c = pts[i]
                end = pts[i + 1] if i == len(pts) - 2 else ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
                c1 = (on[0] + 2 / 3 * (c[0] - on[0]), on[1] + 2 / 3 * (c[1] - on[1]))
                c2 = (end[0] + 2 / 3 * (c[0] - end[0]), end[1] + 2 / 3 * (c[1] - end[1]))
                out.append("b " + " ".join(p(q) for q in (c1, c2, end)))
                on = end
            cur = on
    return " ".join(out)


def shapely_to_ass(geom, ox: float = 0.0, oy: float = 0.0, scale: float = 1.0, decimals: int = 2) -> str:
    """Polygons (with holes) -> drawing; exterior and holes wound oppositely so holes stay empty."""
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.geometry.polygon import orient

    def ring(coords):
        pts = list(coords)[:-1]
        fmt = f"%.{decimals}f"
        s = [(fmt % ((x + ox) * scale)).rstrip("0").rstrip(".") + " " + (fmt % ((y + oy) * scale)).rstrip("0").rstrip(".")
             for x, y in pts]
        return "m " + s[0] + " l " + " ".join(s[1:]) if len(s) > 1 else ""

    polys = [geom] if isinstance(geom, Polygon) else list(getattr(geom, "geoms", []))
    out = []
    for poly in polys:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        poly = orient(poly, sign=1.0)
        out.append(ring(poly.exterior.coords))
        out += [ring(r.coords) for r in poly.interiors]
    return " ".join(o for o in out if o)
