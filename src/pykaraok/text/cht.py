"""Simplified -> Traditional Chinese for subtitle lines.

Only the plain text of the chosen styles is converted; override tags, drawings
and every other line stay byte-identical.  Phrase-level conversion uses OpenCC
(s2twp gives Taiwan forms and vocabulary: 著, 裡, 什麼, 餅乾 ...).  Without
OpenCC it falls back to Windows LCMapStringEx, which converts character by
character and gets phrase-dependent characters wrong more often.

Extra rules such as 你=妳 are applied after the conversion.  Lines whose
character count changes are reported: with per-character karaoke timing the
\\k tags would no longer line up.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from ..aegi.karaoke import parse_blocks
from ..ass.document import AssDocument

LCMAP_TRADITIONAL_CHINESE = 0x04000000


def _opencc(mode: str):
    try:
        import opencc
    except ImportError:
        return None
    return opencc.OpenCC(mode).convert


def _lcmap(text: str) -> str:
    import ctypes
    k32 = ctypes.WinDLL("kernel32")
    f = k32.LCMapStringEx
    f.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_int,
                  ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    buf = ctypes.create_unicode_buffer(len(text) * 2 + 8)
    n = f("zh-CN", LCMAP_TRADITIONAL_CHINESE, text, len(text), buf, len(buf), None, None, None)
    return buf.value[:n]


def converter(mode: str = "s2twp"):
    """Return (convert_function, engine_name)."""
    fn = _opencc(mode)
    if fn:
        return fn, f"opencc:{mode}"
    if sys.platform == "win32":
        return _lcmap, "windows:LCMapStringEx (character level)"
    raise RuntimeError("no converter available: pip install opencc")


def convert_markup(text: str, convert, rules: list[tuple[str, str]]) -> str:
    """Convert the plain-text blocks of an event text, keeping tags and drawings."""
    out = []
    for kind, body in parse_blocks(text):
        if kind == "override":
            out.append("{" + body + "}")
        elif kind == "plain":
            # \N, \n, \h must survive: convert the pieces between them
            pieces = []
            i = 0
            while i < len(body):
                j = i
                while j < len(body) and not (body[j] == "\\" and j + 1 < len(body) and body[j + 1] in "Nnh"):
                    j += 1
                seg = convert(body[i:j])
                for a, b in rules:
                    seg = seg.replace(a, b)
                pieces.append(seg)
                if j < len(body):
                    pieces.append(body[j:j + 2])
                i = j + 2
            out.append("".join(pieces))
        else:
            out.append(body)
    return "".join(out)


@dataclass
class ChtReport:
    engine: str
    lines: int = 0
    changed: int = 0
    length_changed: list = field(default_factory=list)
    samples: list = field(default_factory=list)

    def to_dict(self):
        return self.__dict__.copy()


def convert_doc(doc: AssDocument, styles: list[str], mode: str = "s2twp",
                rules: list[tuple[str, str]] | None = None) -> ChtReport:
    convert, engine = converter(mode)
    rules = rules or []
    rep = ChtReport(engine)
    for i, e in enumerate(doc.events, 1):
        if e["style"] not in styles:
            continue
        head = e["effect"].strip().split(" ")[0].lower() if e["effect"].strip() else ""
        if head in ("template", "code", "mixin", "note") or e["effect"] == "fx":
            continue
        rep.lines += 1
        new = convert_markup(e["text"], convert, rules)
        if new != e["text"]:
            def plain(t):
                return "".join(b for k, b in parse_blocks(t) if k == "plain")
            if len(plain(new)) != len(plain(e["text"])):
                rep.length_changed.append({"event": i, "before": plain(e["text"]), "after": plain(new)})
            if len(rep.samples) < 5:
                rep.samples.append({"before": e["text"], "after": new})
            e["text"] = new
            e.pop("raw", None)
            rep.changed += 1
    return rep
