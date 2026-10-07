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

_POS = re.compile(r"\\(?:pos|move)\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)")


def source_lines(doc: AssDocument, styles: list[str] | None = None) -> list[dict]:
    """The lines the effect was generated from: karaoke/kara template sources, else plain dialogue."""
    kara = [e for e in doc.events if e["effect"].lower() in ("karaoke", "kara")]
    lines = kara or [e for e in doc.events if not e["comment"] and e["effect"] != "fx"]
    if styles:
        lines = [e for e in lines if e["style"] in styles]
    return sorted(lines, key=lambda e: (e["start_time"], e["style"]))


def auto_bands(doc: AssDocument, lines: list[dict], size: tuple[int, int]) -> list[tuple[int, int, int, int]]:
    """Horizontal bands that contain the effect, from fx positions (clustered), else by alignment."""
    w, h = size
    resx, resy = doc.resolution()
    sy = h / resy
    ys = []
    for e in doc.events:
        if e["effect"] == "fx" and not e["comment"]:
            m = _POS.search(e["text"])
            if m:
                ys.append(float(m.group(2)) * sy)
    if not ys:
        aligns = [doc.style(e["style"])["align"] for e in lines if doc.style(e["style"])]
        a = max(set(aligns), key=aligns.count) if aligns else 2
        if a in (7, 8, 9):
            return [(0, 0, w, int(h * 0.34))]
        if a in (4, 5, 6):
            return [(0, int(h * 0.3), w, int(h * 0.4))]
        return [(0, int(h * 0.66), w, h - int(h * 0.66))]
    ys.sort()
    # drop 1% outliers on each side, then split where the gap is large
    k = len(ys) // 100
    ys = ys[k:len(ys) - k] or ys
    clusters = [[ys[0]]]
    for y in ys[1:]:
        if y - clusters[-1][-1] > 0.18 * h:
            clusters.append([y])
        else:
            clusters[-1].append(y)
    bands = []
    pad = 0.08 * h
    for c in clusters:
        top, bot = max(0.0, c[0] - pad), min(float(h), c[-1] + pad)
        if bot - top < 0.18 * h:
            mid = (top + bot) / 2
            top, bot = max(0.0, mid - 0.09 * h), min(float(h), mid + 0.09 * h)
        if bands and top <= bands[-1][1]:
            bands[-1][1] = max(bands[-1][1], bot)
        else:
            bands.append([top, bot])
    if sum(b - a for a, b in bands) > 0.8 * h:
        return [(0, 0, w, h)]
    return [(0, int(a), w, int(b - a)) for a, b in bands]


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
