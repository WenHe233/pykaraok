"""aegisub.text_extents on Windows, ported from Aegisub's CalculateTextExtents
(src/auto4_base.cpp).  Uses the same GDI calls, so widths match what Aegisub
itself computes when it applies a template.

Fonts in the given directories are loaded with AddFontResourceExW(FR_PRIVATE):
visible to this process only, nothing is installed.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

if sys.platform != "win32":  # pragma: no cover
    raise ImportError("GDI metrics are only available on Windows")

_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

FR_PRIVATE = 0x10
MM_TEXT = 1
OUT_TT_PRECIS = 4
CLIP_DEFAULT_PRECIS = 0
ANTIALIASED_QUALITY = 4
FW_NORMAL, FW_BOLD = 400, 700


class LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
                ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
                ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
                ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
                ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
                ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
                ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", wintypes.WCHAR * 32)]


class TEXTMETRICW(ctypes.Structure):
    _fields_ = [("tmHeight", wintypes.LONG), ("tmAscent", wintypes.LONG),
                ("tmDescent", wintypes.LONG), ("tmInternalLeading", wintypes.LONG),
                ("tmExternalLeading", wintypes.LONG), ("tmAveCharWidth", wintypes.LONG),
                ("tmMaxCharWidth", wintypes.LONG), ("tmWeight", wintypes.LONG),
                ("tmOverhang", wintypes.LONG), ("tmDigitizedAspectX", wintypes.LONG),
                ("tmDigitizedAspectY", wintypes.LONG), ("tmFirstChar", wintypes.WCHAR),
                ("tmLastChar", wintypes.WCHAR), ("tmDefaultChar", wintypes.WCHAR),
                ("tmBreakChar", wintypes.WCHAR), ("tmItalic", wintypes.BYTE),
                ("tmUnderlined", wintypes.BYTE), ("tmStruckOut", wintypes.BYTE),
                ("tmPitchAndFamily", wintypes.BYTE), ("tmCharSet", wintypes.BYTE)]


_gdi32.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
_gdi32.AddFontResourceExW.restype = ctypes.c_int
_gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
_gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
_gdi32.SetMapMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
_gdi32.CreateFontIndirectW.restype = ctypes.c_void_p
_gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]
_gdi32.SelectObject.restype = ctypes.c_void_p
_gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.GetTextExtentPoint32W.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                         ctypes.POINTER(wintypes.SIZE)]
_gdi32.GetTextMetricsW.argtypes = [ctypes.c_void_p, ctypes.POINTER(TEXTMETRICW)]
_gdi32.GetTextFaceW.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.LPWSTR]
_gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
_gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

FONT_EXTS = (".ttf", ".otf", ".ttc", ".otc", ".fon")

_loaded: set[str] = set()


def load_font_file(path: str | Path) -> bool:
    key = str(Path(path).resolve()).lower()
    if key in _loaded:
        return True
    ok = _gdi32.AddFontResourceExW(str(Path(path).resolve()), FR_PRIVATE, None) > 0
    if ok:
        _loaded.add(key)
    return ok


def load_font_dir(folder: str | Path) -> int:
    n = 0
    folder = Path(folder)
    if folder.is_file():
        return int(load_font_file(folder))
    for p in sorted(folder.rglob("*")):
        if p.suffix.lower() in FONT_EXTS and load_font_file(p):
            n += 1
    return n


class GdiMetrics:
    name = "gdi"

    def __init__(self, font_dirs=()):
        self.warnings: list[str] = []
        self._cache: dict[tuple, tuple[float, float, float, float]] = {}
        self._fonts: dict[tuple, int] = {}
        self._faces: dict[str, str] = {}
        for d in font_dirs:
            load_font_dir(d)
        self._dc = _gdi32.CreateCompatibleDC(None)
        _gdi32.SetMapMode(self._dc, MM_TEXT)

    def close(self):
        for h in self._fonts.values():
            _gdi32.DeleteObject(h)
        self._fonts.clear()
        if self._dc:
            _gdi32.DeleteDC(self._dc)
            self._dc = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _font(self, fontname, height, bold, italic, underline, strikeout, charset):
        key = (fontname, height, bold, italic, underline, strikeout, charset)
        h = self._fonts.get(key)
        if h is None:
            lf = LOGFONTW()
            lf.lfHeight = height
            lf.lfWeight = FW_BOLD if bold else FW_NORMAL
            lf.lfItalic = 1 if italic else 0
            lf.lfUnderline = 1 if underline else 0
            lf.lfStrikeOut = 1 if strikeout else 0
            lf.lfCharSet = charset
            lf.lfOutPrecision = OUT_TT_PRECIS
            lf.lfClipPrecision = CLIP_DEFAULT_PRECIS
            lf.lfQuality = ANTIALIASED_QUALITY
            lf.lfPitchAndFamily = 0
            lf.lfFaceName = fontname[:31]
            h = _gdi32.CreateFontIndirectW(ctypes.byref(lf))
            if not h:
                raise RuntimeError(f"CreateFontIndirect failed for {fontname!r}")
            self._fonts[key] = h
        return h

    def resolved_face(self, fontname: str, bold=False, italic=False) -> str:
        """The face GDI actually selects for `fontname` (differs when the font is missing)."""
        h = self._font(fontname, 64 * 64, bold, italic, False, False, 1)
        old = _gdi32.SelectObject(self._dc, h)
        buf = ctypes.create_unicode_buffer(64)
        _gdi32.GetTextFaceW(self._dc, 64, buf)
        _gdi32.SelectObject(self._dc, old)
        return buf.value

    def text_extents(self, style: dict, text: str) -> tuple[float, float, float, float]:
        fontname = style["fontname"]
        fontsize = float(style["fontsize"])
        spacing = float(style.get("spacing", 0) or 0)
        scale_x = float(style.get("scale_x", 100))
        scale_y = float(style.get("scale_y", 100))
        bold, italic = bool(style.get("bold")), bool(style.get("italic"))
        underline, strikeout = bool(style.get("underline")), bool(style.get("strikeout"))
        charset = int(style.get("encoding", 1)) & 0xFF
        key = (fontname, fontsize, bold, italic, underline, strikeout, charset, spacing, scale_x, scale_y, text)
        hit = self._cache.get(key)
        if hit is not None:
            return hit

        if fontname not in self._faces:
            face = self.resolved_face(fontname, bold, italic)
            self._faces[fontname] = face
            if face.lower() != fontname[:31].lower():
                self.warnings.append(f"font {fontname!r} not found by GDI, measured with {face!r} instead")

        fs64 = fontsize * 64
        sp64 = spacing * 64
        h = self._font(fontname, int(fs64), bold, italic, underline, strikeout, charset)
        old = _gdi32.SelectObject(self._dc, h)
        units = text.encode("utf-16-le")
        n16 = len(units) // 2
        buf = (ctypes.c_char * max(len(units), 2)).from_buffer_copy(units or b"\0\0")
        sz = wintypes.SIZE()
        if sp64 != 0:
            width = 0.0
            height = 0.0
            for i in range(n16):
                _gdi32.GetTextExtentPoint32W(self._dc, ctypes.byref(buf, 2 * i), 1, ctypes.byref(sz))
                width += sz.cx + sp64
                height = float(sz.cy)
        else:
            _gdi32.GetTextExtentPoint32W(self._dc, buf, n16, ctypes.byref(sz))
            width, height = float(sz.cx), float(sz.cy)
        tm = TEXTMETRICW()
        _gdi32.GetTextMetricsW(self._dc, ctypes.byref(tm))
        _gdi32.SelectObject(self._dc, old)
        res = (scale_x / 100 * width / 64, scale_y / 100 * height / 64,
               scale_y / 100 * tm.tmDescent / 64, scale_y / 100 * tm.tmExternalLeading / 64)
        self._cache[key] = res
        return res
