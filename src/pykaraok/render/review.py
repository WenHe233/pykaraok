"""Per-line review sheets: every lyric line at its entry, middle and exit."""
from __future__ import annotations

import re
from pathlib import Path

from ..ass.document import AssDocument
from . import ffmpeg as rf

PHASES = {
    # name: function(start_s, end_s) -> time
    "in": lambda s, e: s + min(0.12, (e - s) / 4),
    "in+": lambda s, e: s + min(0.45, (e - s) / 3),
    "mid": lambda s, e: (s + e) / 2,
    "out-": lambda s, e: max(s, e - 0.35),
    "out": lambda s, e: e + 0.15,
}

_AN = re.compile(r"\\an([1-9])")
_POS = re.compile(r"\\(?:pos|move)\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)")


def source_lines(doc: AssDocument, styles: list[str] | None = None) -> list[dict]:
    """The lines the effect was generated from: karaoke/kara template sources, else plain dialogue."""
    kara = [e for e in doc.events if e["effect"].lower() in ("karaoke", "kara")]
    lines = kara or [e for e in doc.events if not e["comment"] and e["effect"] != "fx"]
    if styles:
        lines = [e for e in lines if e["style"] in styles]
    return sorted(lines, key=lambda e: (e["start_time"], e["style"]))


def _style_band(doc: AssDocument, e: dict, size) -> tuple[float, float]:
    """Vertical extent of a plain line from its style's alignment and vertical margin (no fx)."""
    w, h = size
    resx, resy = doc.resolution()
    sy = h / resy
    st = doc.style(e["style"]) or {"align": 2, "margin_t": 20, "fontsize": 48, "scale_y": 100}
    m = _AN.search(e["text"])
    an = int(m.group(1)) if m else st["align"]
    mv = (e["margin_t"] or st["margin_t"]) * sy
    fs = st["fontsize"] * st["scale_y"] / 100 * sy
    pm = _POS.search(e["text"])
    if pm:
        y = float(pm.group(2)) * sy
        top = y if an in (7, 8, 9) else (y - fs / 2 if an in (4, 5, 6) else y - fs)
    elif an in (7, 8, 9):
        top = mv
    elif an in (4, 5, 6):
        top = h / 2 - fs / 2
    else:
        top = h - mv - fs
    return top, top + fs


def auto_bands(doc: AssDocument, lines: list[dict], size: tuple[int, int]) -> list[tuple[int, int, int, int]]:
    """Bands that contain the subtitles: clustered fx positions, else each lyric line's style placement.

    All bands share one horizontal range (the span of the fx positions plus a margin), so
    narrow effects are shown larger.
    """
    w, h = size
    resx, resy = doc.resolution()
    sx, sy = w / resx, h / resy
    spans = []          # (top, bottom) per item
    xs = []
    for e in doc.events:
        if e["effect"] == "fx" and not e["comment"]:
            m = _POS.search(e["text"])
            if m:
                y = float(m.group(2)) * sy
                spans.append((y, y))
                xs.append(float(m.group(1)) * sx)
    pad = 0.08 * h
    if not spans:
        spans = [_style_band(doc, e, size) for e in lines]
        pad = 0.04 * h
    if not spans:
        return [(0, 0, w, h)]
    spans.sort()
    k = len(spans) // 100 if len(spans) > 200 else 0
    spans = spans[k:len(spans) - k] or spans
    clusters = [[spans[0][0], spans[0][1]]]
    for top, bot in spans[1:]:
        if top - clusters[-1][1] > 0.18 * h:
            clusters.append([top, bot])
        else:
            clusters[-1][1] = max(clusters[-1][1], bot)
    bands = []
    for top, bot in clusters:
        top, bot = max(0.0, top - pad), min(float(h), bot + pad)
        if bot - top < 0.14 * h:
            mid = (top + bot) / 2
            top, bot = max(0.0, mid - 0.07 * h), min(float(h), mid + 0.07 * h)
        if bands and top <= bands[-1][1]:
            bands[-1][1] = max(bands[-1][1], bot)
        else:
            bands.append([top, bot])
    if sum(b - a for a, b in bands) > 0.8 * h:
        return [(0, 0, w, h)]
    x0, x1 = 0, w
    if len(xs) >= 4:
        xs.sort()
        k = len(xs) // 50
        lo, hi = xs[k], xs[len(xs) - 1 - k]
        margin = max(0.06 * w, 120 * sx)
        x0, x1 = int(max(0, lo - margin)), int(min(w, hi + margin))
        if x1 - x0 < 0.35 * w:
            mid = (x0 + x1) // 2
            x0, x1 = int(max(0, mid - 0.175 * w)), int(min(w, mid + 0.175 * w))
    return [(x0, int(a), x1 - x0, int(b - a)) for a, b in bands]


def line_sheets(ass_path, out_prefix, source: rf.Source, font_dirs=None, styles=None,
                phases=("in", "in+", "mid", "out-", "out"), per_sheet: int = 8, crop="auto",
                width: int = 480, first: int = 1, count: int | None = None) -> list[dict]:
    doc = AssDocument.load(ass_path)
    # lines shown together (e.g. JP + CN with the same timing) share one row
    groups: list[list[dict]] = []
    for e in source_lines(doc, styles):
        if groups and (groups[-1][0]["start_time"], groups[-1][0]["end_time"]) == (e["start_time"], e["end_time"]):
            groups[-1].append(e)
        else:
            groups.append([e])
    groups = groups[first - 1:]
    if count:
        groups = groups[:count]
    lines = [g[0] for g in groups]
    if crop == "auto":
        crop = auto_bands(doc, [e for g in groups for e in g], source.size)
    elif crop in ("full", None):
        crop = None
    results = []
    for k in range(0, len(lines), per_sheet):
        chunk = lines[k:k + per_sheet]
        times, caps = [], []
        for j, e in enumerate(chunk):
            s, en = e["start_time"] / 1000, e["end_time"] / 1000
            for ph in phases:
                times.append(PHASES[ph](s, en))
                caps.append(f"#{first + k + j} {ph}")
        out = Path(f"{out_prefix}_{k // per_sheet + 1:02d}.png")
        info = rf.sample_sheet(ass_path, times, out, source, font_dirs, cols=len(phases), crop=crop,
                               width=width, captions=caps)
        info["lines"] = [{"index": first + k + j, "start": e["start_time"], "end": e["end_time"],
                          "styles": [x["style"] for x in groups[k + j]],
                          "text": " / ".join(re.sub(r"\{[^}]*\}", "", x["text"])[:40] for x in groups[k + j])}
                         for j, e in enumerate(chunk)]
        info["crop"] = crop
        results.append(info)
    return results
