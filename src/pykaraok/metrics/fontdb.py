"""Font lookup by family name and GDI-compatible metrics computed with fontTools.

FontIndex is used everywhere a font file is needed (glyph coverage checks,
glyph outlines, the fontsdir for rendering).  FontToolsMetrics is the
text_extents backend on systems without GDI: it reproduces GDI's cell-height
sizing (font size = usWinAscent + usWinDescent) and per-glyph advance
rounding at 64x size, which is what Aegisub measures on Windows.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

FONT_EXTS = (".ttf", ".otf", ".ttc", ".otc")


@dataclass
class FontFace:
    path: Path
    index: int
    names: set[str] = field(default_factory=set)       # lower-cased family / full / postscript names
    family: str = ""
    weight: int = 400
    italic: bool = False
    _tt: object = None

    def ttfont(self):
        if self._tt is None:
            from fontTools.ttLib import TTFont
            self._tt = TTFont(str(self.path), fontNumber=self.index, lazy=True)
        return self._tt


def system_font_dirs() -> list[Path]:
    dirs = []
    if sys.platform == "win32":
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        dirs.append(windir / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        dirs += [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library" / "Fonts"]
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".local/share/fonts",
                 Path.home() / ".fonts"]
    return [d for d in dirs if d.is_dir()]


class FontIndex:
    def __init__(self, font_dirs=(), include_system: bool = True):
        self.faces: list[FontFace] = []
        self._by_name: dict[str, list[FontFace]] = {}
        self.user_dirs = [Path(d) for d in font_dirs]
        for d in self.user_dirs:
            self.add_path(d)
        self._system_loaded = False
        self._include_system = include_system

    def add_path(self, path: Path):
        path = Path(path)
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.suffix.lower() in FONT_EXTS)
        for f in files:
            self._add_file(f)

    def _add_file(self, f: Path):
        from fontTools.ttLib import TTFont, TTCollection
        try:
            if f.suffix.lower() in (".ttc", ".otc"):
                n = len(TTCollection(str(f), lazy=True).fonts)
            else:
                n = 1
        except Exception:
            return
        for idx in range(n):
            try:
                tt = TTFont(str(f), fontNumber=idx, lazy=True)
                names = set()
                family = ""
                for rec in tt["name"].names:
                    if rec.nameID in (1, 4, 6, 16):
                        try:
                            s = rec.toUnicode().strip()
                        except Exception:
                            continue
                        if s:
                            names.add(s.lower())
                            if rec.nameID == 1 and (not family or rec.langID == 0x409):
                                family = s
                os2 = tt["OS/2"] if "OS/2" in tt else None
                weight = os2.usWeightClass if os2 else 400
                italic = bool(os2.fsSelection & 1) if os2 else False
                tt.close()
            except Exception:
                continue
            face = FontFace(f, idx, names, family, weight, italic)
            self.faces.append(face)
            for nm in names:
                self._by_name.setdefault(nm, []).append(face)

    def _ensure_system(self):
        if not self._system_loaded and self._include_system:
            self._system_loaded = True
            for d in system_font_dirs():
                self.add_path(d)

    def find(self, name: str, bold: bool = False, italic: bool = False, system: bool = True) -> FontFace | None:
        cands = self._by_name.get(name.strip().lower())
        if not cands and system:
            self._ensure_system()
            cands = self._by_name.get(name.strip().lower())
        if not cands:
            return None
        want_w = 700 if bold else 400

        def score(face: FontFace):
            return (abs(face.weight - want_w) if bold else 0) + (0 if face.italic == italic else 300) + \
                (abs(face.weight - 400) if not bold else 0) * 0.01
        return min(cands, key=score)

    def find_in_user_dirs(self, name: str) -> FontFace | None:
        return self.find(name, system=False)


class FontToolsMetrics:
    """GDI-compatible text extents from font tables (no font linking or fallback)."""
    name = "fonttools"

    def __init__(self, font_dirs=(), index: FontIndex | None = None):
        self.index = index or FontIndex(font_dirs)
        self.warnings: list[str] = []
        self._warned: set[str] = set()
        self._cache: dict[tuple, tuple[float, float, float, float]] = {}
        self._info: dict[tuple, dict] = {}

    def _font_info(self, name: str, bold: bool, italic: bool) -> dict | None:
        key = (name, bold, italic)
        if key in self._info:
            return self._info[key]
        face = self.index.find(name, bold, italic)
        info = None
        if face is not None:
            tt = face.ttfont()
            os2 = tt["OS/2"] if "OS/2" in tt else None
            hhea = tt["hhea"]
            win_asc = os2.usWinAscent if os2 else hhea.ascent
            win_desc = os2.usWinDescent if os2 else -hhea.descent
            info = {
                "cmap": tt.getBestCmap() or {},
                "hmtx": tt["hmtx"].metrics,
                "upm": tt["head"].unitsPerEm,
                "win_asc": win_asc, "win_desc": win_desc,
                "hhea_asc": hhea.ascent, "hhea_desc": hhea.descent, "hhea_gap": hhea.lineGap,
                "notdef": tt["hmtx"].metrics.get(".notdef", (tt["head"].unitsPerEm // 2, 0))[0],
                "glyph_order": tt.getGlyphOrder(),
            }
        elif name not in self._warned:
            self._warned.add(name)
            self.warnings.append(f"font {name!r} not found; using fallback widths (CJK 1em, others 0.55em)")
        self._info[key] = info
        return info

    def text_extents(self, style: dict, text: str) -> tuple[float, float, float, float]:
        fontname = style["fontname"]
        fontsize = float(style["fontsize"])
        spacing = float(style.get("spacing", 0) or 0)
        scale_x = float(style.get("scale_x", 100))
        scale_y = float(style.get("scale_y", 100))
        bold, italic = bool(style.get("bold")), bool(style.get("italic"))
        key = (fontname, fontsize, bold, italic, spacing, scale_x, scale_y, text)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        fs64 = int(fontsize * 64)
        sp64 = spacing * 64
        units16 = len(text.encode("utf-16-le")) // 2
        info = self._font_info(fontname, bold, italic)
        if info is None:
            w = sum((fs64 if ord(c) >= 0x2E80 else fs64 * 0.55) for c in text)
            height, descent, extlead = float(fs64), fs64 * 0.12, 0.0
        else:
            cell = (info["win_asc"] + info["win_desc"]) or (info["hhea_asc"] - info["hhea_desc"]) or info["upm"]
            k = fs64 / cell
            w = 0
            missing = []
            for c in text:
                g = info["cmap"].get(ord(c))
                if g is None:
                    adv = info["notdef"]
                    missing.append(c)
                else:
                    adv = info["hmtx"].get(g, (info["notdef"], 0))[0]
                w += round(adv * k)
            if missing:
                msg = f"font {fontname!r} has no glyph for {''.join(sorted(set(missing)))!r}"
                if msg not in self._warned:
                    self._warned.add(msg)
                    self.warnings.append(msg)
            height = float(round(info["win_asc"] * k) + round(info["win_desc"] * k))
            descent = float(round(info["win_desc"] * k))
            gap = info["hhea_gap"] - ((info["win_asc"] + info["win_desc"]) - (info["hhea_asc"] - info["hhea_desc"]))
            extlead = float(max(0, round(gap * k)))
        if sp64 != 0:
            w += sp64 * units16
        res = (scale_x / 100 * w / 64, scale_y / 100 * height / 64,
               scale_y / 100 * descent / 64, scale_y / 100 * extlead / 64)
        self._cache[key] = res
        return res


def make_metrics(backend: str = "auto", font_dirs=()):
    """Return a text_extents backend. backend: auto | gdi | fonttools."""
    if backend in ("auto", "gdi") and sys.platform == "win32":
        from .gdi import GdiMetrics
        return GdiMetrics(font_dirs)
    if backend == "gdi":
        raise RuntimeError("the GDI backend needs Windows; use --metrics fonttools")
    return FontToolsMetrics(font_dirs)
