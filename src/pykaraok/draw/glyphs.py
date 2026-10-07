"""Glyph outlines -> ASS \\p drawings.

Uses for templates:
  * replace characters the chosen font lacks with drawings (taken from another
    font, or composed from parts of glyphs of the same font)
  * text-to-shape effects prepared in Python and pasted into a code once table

Coordinates: the drawing's origin is the top-left of the GDI text cell, so
`{\\an7\\pos(left, top)\\p1}` with the line's left/top puts it where the glyph
would be drawn.  1 drawing unit = 1 px at \\p1 (use scale=8 with \\p4 for
sub-pixel precision).
"""
from __future__ import annotations

from dataclasses import dataclass

from fontTools.pens.basePen import BasePen

from ..metrics.fontdb import FontFace, FontIndex


class _AssPen(BasePen):
    """Collects contours as ASS commands; quadratic curves are converted to cubic exactly."""

    def __init__(self, glyphset, xform):
        super().__init__(glyphset)
        self.xform = xform
        self.parts: list[str] = []
        self.dec = 2

    def _p(self, pt):
        x, y = self.xform(pt)
        fmt = f"%.{self.dec}f"
        return (fmt % x).rstrip("0").rstrip(".") + " " + (fmt % y).rstrip("0").rstrip(".")

    def _moveTo(self, pt):
        self.parts.append("m " + self._p(pt))

    def _lineTo(self, pt):
        self.parts.append("l " + self._p(pt))

    def _curveToOne(self, p1, p2, p3):
        self.parts.append("b " + self._p(p1) + " " + self._p(p2) + " " + self._p(p3))

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
        c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
        self._curveToOne(c1, c2, p2)

    def _closePath(self):
        pass


@dataclass
class GlyphDrawing:
    char: str
    drawing: str
    advance: float     # px
    cell_height: float  # px (= font size for GDI-style sizing)
    font: str


def _metrics(face: FontFace):
    tt = face.ttfont()
    os2 = tt["OS/2"] if "OS/2" in tt else None
    hhea = tt["hhea"]
    asc = os2.usWinAscent if os2 else hhea.ascent
    desc = os2.usWinDescent if os2 else -hhea.descent
    return tt, asc, desc


def glyph_drawing(face: FontFace, ch: str, size: float, x: float = 0.0, y: float = 0.0,
                  scale: float = 1.0, decimals: int = 2, sx: float = 1.0, sy: float = 1.0) -> GlyphDrawing:
    """Outline of one character, sized like GDI/libass size `size` (cell height)."""
    tt, asc, desc = _metrics(face)
    cmap = tt.getBestCmap() or {}
    gname = cmap.get(ord(ch))
    if gname is None:
        raise KeyError(f"{face.family or face.path.name} has no glyph for {ch!r}")
    k = size / (asc + desc)
    gs = tt.getGlyphSet()

    def xf(pt):
        return ((x + pt[0] * k * sx) * scale, (y + (asc - pt[1]) * k * sy) * scale)

    pen = _AssPen(gs, xf)
    pen.dec = decimals
    gs[gname].draw(pen)
    adv = tt["hmtx"][gname][0] * k * sx
    return GlyphDrawing(ch, " ".join(pen.parts), adv, size, face.family)


def text_drawing(face: FontFace, text: str, size: float, spacing: float = 0.0, scale: float = 1.0,
                 decimals: int = 2) -> tuple[str, float]:
    """Whole string as one drawing (no kerning, like GDI). Returns (drawing, width_px)."""
    parts = []
    x = 0.0
    for ch in text:
        if ch.isspace():
            g = glyph_drawing(face, " ", size) if ord(" ") in (face.ttfont().getBestCmap() or {}) else None
            x += (g.advance if g else size / 3) + spacing
            continue
        g = glyph_drawing(face, ch, size, x=x, scale=scale, decimals=decimals)
        parts.append(g.drawing)
        x += g.advance + spacing
    return " ".join(p for p in parts if p), x


def resolve_face(name_or_path: str, font_dirs=(), bold=False, italic=False) -> FontFace:
    from pathlib import Path
    p = Path(name_or_path)
    if p.suffix.lower() in (".ttf", ".otf", ".ttc", ".otc") and p.exists():
        idx = FontIndex([p], include_system=False)
        return idx.faces[0]
    idx = FontIndex(font_dirs)
    face = idx.find(name_or_path, bold, italic)
    if face is None:
        raise KeyError(f"font {name_or_path!r} not found")
    return face
