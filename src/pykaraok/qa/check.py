"""Static checks for effect subtitle files.

Each check returns findings: {"check", "level" (error|warn|info), "message", ...data}.
Render-based checks (performance, steady-state diff, one-frame jumps) live in
qa/frames.py and are run by `pykaraok check` when a video or --render is given.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from ..aegi.karaoke import parse_blocks, parse_syllables, split_override
from ..ass.document import AssDocument

# libass ass_parse.c: these tags set detect_collisions = 0
_NO_COLLIDE = re.compile(r"\\(pos|move|org|t)\s*\(")
_TEMPLATE_HEAD = ("template", "code", "mixin")


def _f(check, level, message, **data):
    d = {"check": check, "level": level, "message": message}
    d.update(data)
    return d


def _head(effect: str) -> str:
    return effect.strip().split(" ")[0].lower() if effect.strip() else ""


def _visible(e) -> bool:
    return not e["comment"]


# ---------------------------------------------------------------- template rules

def check_template_position(doc: AssDocument) -> list[dict]:
    """Aegisub enables 'Apply karaoke template' only if a template line is among the first 50 dialogue lines."""
    first = None
    for i, e in enumerate(doc.events, 1):
        if _head(e["effect"]) == "template":
            first = i
            break
    if first is None:
        return [_f("template_position", "info", "no template lines in this file")]
    if first > 51:
        return [_f("template_position", "error",
                   f"first template line is event #{first}; Aegisub only looks at the first 50 dialogue lines, "
                   "so 'Apply karaoke template' would be disabled. Move template lines to the top.",
                   first_template_event=first)]
    return [_f("template_position", "info", f"first template line is event #{first}", first_template_event=first)]


# ---------------------------------------------------------------- basic sanity

def _strip_tags(text: str) -> tuple[str, bool]:
    plain, drawing = [], False
    for kind, body in parse_blocks(text):
        if kind == "plain":
            plain.append(body)
        elif kind == "drawing" and body.strip():
            drawing = True
    return "".join(plain), drawing


def check_fx_sanity(doc: AssDocument) -> list[dict]:
    out = []
    fx = [e for e in doc.events if e["effect"] == "fx"]
    empty = [e for e in fx if _visible(e) and not "".join(_strip_tags(e["text"])[0].split()) and not _strip_tags(e["text"])[1]]
    bad_dur = [e for e in doc.events if _visible(e) and e["end_time"] <= e["start_time"]]
    huge = [e for e in doc.events if len(e["text"]) > 6000]
    if empty:
        out.append(_f("fx_sanity", "info", f"{len(empty)} fx lines draw nothing (no text or drawing)",
                      count=len(empty), example=empty[0]["text"][:160]))
    if bad_dur:
        out.append(_f("fx_sanity", "warn", f"{len(bad_dur)} visible lines have end <= start", count=len(bad_dur),
                      example=bad_dur[0]["text"][:160]))
    if huge:
        out.append(_f("fx_sanity", "warn", f"{len(huge)} lines are longer than 6000 characters", count=len(huge)))
    return out


def check_karaoke_timing(doc: AssDocument) -> list[dict]:
    out = []
    issues = []
    short = 0
    for i, e in enumerate(doc.events, 1):
        if e["effect"].lower() not in ("karaoke", "kara"):
            continue
        syls = [s for s in parse_syllables(e["text"], e["start_time"])]
        ktotal = sum(s["duration"] for s in syls)
        dur = e["end_time"] - e["start_time"]
        if "\\k" not in e["text"] and "\\K" not in e["text"]:
            continue
        if abs(ktotal - dur) > 50:
            issues.append({"event": i, "k_total_ms": ktotal, "line_ms": dur})
        short += sum(1 for s in syls if 0 < s["duration"] < 50)
    if issues:
        out.append(_f("karaoke_timing", "info",
                      f"{len(issues)} karaoke lines have a \\k total that differs from the line duration by > 50 ms "
                      "(fine when only a leading {\\k1} is used)", lines=issues[:10]))
    if short:
        out.append(_f("karaoke_timing", "info", f"{short} syllables are shorter than 50 ms", count=short))
    return out


# ---------------------------------------------------------------- layout

def _collides(e) -> bool:
    if not _visible(e):
        return False
    eff = e["effect"].lower()
    if eff.startswith("banner;") or eff.startswith("scroll up;") or eff.startswith("scroll down;"):
        return False
    return not _NO_COLLIDE.search(e["text"])


def check_collisions(doc: AssDocument) -> list[dict]:
    """libass moves unpositioned events that overlap in time (the "jumping line" bug of earlier projects)."""
    evs = sorted((e for e in doc.events if _collides(e)), key=lambda e: e["start_time"])
    overlapping = []
    active: list[dict] = []
    for e in evs:
        active = [a for a in active if a["end_time"] > e["start_time"]]
        for a in active:
            overlapping.append((a, e))
        active.append(e)
    if not overlapping:
        n = len(evs)
        return [_f("collisions", "info", f"{n} visible lines take part in libass collision handling; none overlap in time")]
    ex = [{"a": f"{a['style']} {a['start_time']}-{a['end_time']} {a['text'][:80]}",
           "b": f"{b['style']} {b['start_time']}-{b['end_time']} {b['text'][:80]}"} for a, b in overlapping[:5]]
    fx_pairs = sum(1 for a, b in overlapping if a["effect"] == "fx" or b["effect"] == "fx")
    return [_f("collisions", "warn" if fx_pairs else "info",
               f"{len(overlapping)} pairs of unpositioned lines overlap in time; libass will push one of them "
               "away (lines jump or stack). Give fx lines \\pos/\\move, or an empty \\t that never starts.",
               pairs=len(overlapping), fx_pairs=fx_pairs, examples=ex)]


def check_concurrency(doc: AssDocument, source_styles: list[str] | None = None) -> list[dict]:
    """Peak number of simultaneous events, and how many lyric lines of one style are on screen at once."""
    out = []
    vis = [e for e in doc.events if _visible(e)]
    points = sorted([(e["start_time"], 1) for e in vis] + [(e["end_time"], -1) for e in vis])
    cur = peak = 0
    peak_t = 0
    for t, d in points:
        cur += d
        if cur > peak:
            peak, peak_t = cur, t
    out.append(_f("concurrency", "info", f"peak {peak} events on screen at {peak_t / 1000:.2f}s",
                  peak=peak, at_ms=peak_t))
    # source lyric lines per style
    src = [e for e in doc.events if e["effect"].lower() in ("karaoke", "kara")] or \
          [e for e in vis if e["effect"] != "fx"]
    by_style = defaultdict(list)
    for e in src:
        if source_styles and e["style"] not in source_styles:
            continue
        by_style[e["style"]].append(e)
    multi = {}
    for st, lines in by_style.items():
        lines.sort(key=lambda e: e["start_time"])
        n = sum(1 for a, b in zip(lines, lines[1:]) if b["start_time"] < a["end_time"])
        if n:
            multi[st] = n
    if multi:
        out.append(_f("concurrency", "info",
                      "lyric lines of the same style overlap in time (two rows on screen at once): "
                      + ", ".join(f"{k}: {v}" for k, v in multi.items()), overlaps=multi))
    return out


def check_stats(doc: AssDocument, path: str | Path | None = None) -> list[dict]:
    fx = [e for e in doc.events if e["effect"] == "fx"]
    layers = Counter(int(e["layer"]) for e in fx)
    data = {
        "events": len(doc.events), "fx_lines": len(fx),
        "fx_by_layer": dict(sorted(layers.items())),
        "fx_text_bytes": sum(len(e["text"].encode("utf-8")) for e in fx),
    }
    if path:
        data["file_bytes"] = Path(path).stat().st_size
    return [_f("stats", "info", f"{len(doc.events)} events, {len(fx)} fx lines", **data)]


# ---------------------------------------------------------------- fonts

def used_fonts(doc: AssDocument) -> dict[tuple[str, bool, bool], set[str]]:
    """(font, bold, italic) -> characters drawn with it, following \\fn, \\b, \\i and \\r overrides."""
    styles = {s["name"]: s for s in doc.styles}
    out: dict[tuple[str, bool, bool], set[str]] = defaultdict(set)
    for e in doc.events:
        if not _visible(e):
            continue
        st = styles.get(e["style"]) or (doc.styles[0] if doc.styles else None)
        if st is None:
            continue
        font, bold, italic = st["fontname"], st["bold"], st["italic"]
        for kind, body in parse_blocks(e["text"]):
            if kind == "override":
                for tag in split_override(body):
                    if tag.startswith("\\fn"):
                        font = tag[3:].strip() or st["fontname"]
                    elif tag.startswith("\\r"):
                        rs = styles.get(tag[2:].strip()) or st
                        font, bold, italic = rs["fontname"], rs["bold"], rs["italic"]
                    elif re.match(r"\\b\d", tag):
                        v = int(re.match(r"\\b(\d+)", tag).group(1))
                        bold = v == 1 or v >= 700
                    elif re.match(r"\\i\d", tag):
                        italic = tag[2:3] == "1"
            elif kind == "plain":
                text = body.replace("\\N", "").replace("\\n", "").replace("\\h", " ")
                for ch in text:
                    if not ch.isspace():
                        out[(font.lstrip("@"), bold, italic)].add(ch)
    return out


def check_fonts(doc: AssDocument, font_dirs=()) -> list[dict]:
    from ..metrics.fontdb import FontIndex
    idx = FontIndex(font_dirs)
    out = []
    for (font, bold, italic), chars in sorted(used_fonts(doc).items()):
        face = idx.find(font, bold, italic)
        if face is None:
            out.append(_f("fonts", "error", f"font {font!r} is not in the font dirs or installed",
                          font=font, chars=len(chars)))
            continue
        cmap = face.ttfont().getBestCmap() or {}
        missing = sorted(c for c in chars if ord(c) not in cmap)
        where = "font dirs" if any(str(face.path).startswith(str(Path(d).resolve())) or
                                   str(face.path).startswith(str(d)) for d in font_dirs) else "system"
        if missing:
            out.append(_f("fonts", "error",
                          f"{font!r} has no glyph for {''.join(missing)}: the renderer will substitute another font",
                          font=font, missing="".join(missing), file=str(face.path)))
        else:
            out.append(_f("fonts", "info", f"{font!r}: {len(chars)} characters covered ({where})",
                          font=font, file=str(face.path)))
    return out


# ---------------------------------------------------------------- reapply

def check_reapply(doc: AssDocument, path, options=None, engine: str = "stock") -> list[dict]:
    """Applying the templates again must reproduce the file (what users get when they press Apply in Aegisub)."""
    from ..aegi.templater import apply_templates
    from .compare import compare_docs
    again = AssDocument.load(path)
    res = apply_templates(again, engine, options)
    if not res.ok:
        return [_f("reapply", "error", f"re-applying the templates failed: {res.message[:400]}")]
    rep = compare_docs(doc, again)
    if rep.counts.get("identical", 0) == rep.total_a == rep.total_b:
        return [_f("reapply", "info", f"re-applying the templates reproduces all {rep.total_a} fx lines")]
    if rep.total_a == rep.total_b and set(rep.counts) <= {"identical", "time_round"}:
        return [_f("reapply", "info",
                   f"re-applying differs only by centisecond rounding on {rep.counts.get('time_round', 0)} lines "
                   "(the file was produced by a tool that truncates times; Aegisub rounds)", **rep.to_dict())]
    return [_f("reapply", "warn", "re-applying the templates gives different fx lines "
               "(random values not seeded from line data, or fonts differ)", **rep.to_dict())]


def run_static(path, font_dirs=(), reapply: bool = False, options=None, engine: str = "stock") -> list[dict]:
    doc = AssDocument.load(path)
    findings = []
    findings += check_stats(doc, path)
    findings += check_template_position(doc)
    findings += check_fx_sanity(doc)
    findings += check_karaoke_timing(doc)
    findings += check_collisions(doc)
    findings += check_concurrency(doc)
    findings += check_fonts(doc, font_dirs)
    if reapply:
        findings += check_reapply(doc, path, options, engine)
    return findings
