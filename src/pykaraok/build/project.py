"""Build a single-file effect .ass from a template source and the user's lyrics file.

Output layout (what the user accepted in earlier projects):
  * note / template / code lines at the top of [Events], so a template line is
    within the first 50 dialogue lines and Aegisub's Apply menu stays enabled
  * the lyric lines turned into Comment lines with Effect "karaoke" (stock) or
    "kara" (0x539): they are the template input and stay editable
  * the generated fx lines (Effect "fx"), which re-applying in Aegisub replaces
  * every other line of the lyrics file unchanged
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from ..aegi.karaoke import parse_blocks
from ..ass.document import AssDocument, parse_style
from . import source as srcmod
from .luaflat import check_syntax

GENERATED_HEADS = ("template", "code", "mixin", "note")


@dataclass
class BuildResult:
    output: str | None = None
    engine: str = "stock"
    lyric_lines: int = 0
    generated_lines: int = 0
    lyric_styles: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    apply: dict | None = None
    first_template_event: int | None = None

    def to_dict(self):
        return self.__dict__.copy()


def fxlib_source(name: str) -> srcmod.Source:
    p = config.FXLIB_DIR / f"{name}.lua"
    if not p.exists():
        avail = ", ".join(sorted(x.stem for x in config.FXLIB_DIR.glob("*.lua")))
        raise FileNotFoundError(f"fxlib module {name!r} not found (available: {avail})")
    return srcmod.load(p)


def _head(effect: str) -> str:
    return effect.strip().split(" ")[0].lower() if effect.strip() else ""


def _plain_len_cs(e: dict) -> int:
    return max(0, round((e["end_time"] - e["start_time"]) / 10))


def ensure_k(e: dict, mode: str) -> tuple[str, bool]:
    """Add karaoke timing to a line without \\k tags.  mode: keep | line | char."""
    text = e["text"]
    if mode == "keep" or re.search(r"\\[kK][fo]?\d", text):
        return text, False
    total = _plain_len_cs(e)
    if mode == "line":
        return "{\\k%d}" % total + text, True
    # char: spread the duration evenly over visible characters, keeping override blocks in place
    blocks = parse_blocks(text)
    chars = sum(len([c for c in b if not c.isspace()]) for k, b in blocks if k == "plain")
    if chars == 0:
        return "{\\k%d}" % total + text, True
    out, given, seen = [], 0, 0
    for kind, body in blocks:
        if kind == "override":
            out.append("{" + body + "}")
        elif kind != "plain":
            out.append(body)
        else:
            for c in body:
                if c.isspace():
                    out.append(c)
                    continue
                seen += 1
                d = round(total * seen / chars) - given
                given += d
                out.append("{\\k%d}%s" % (d, c))
    return "".join(out), True


def build(source_path, lyrics_path, output=None, engine: str | None = None, lyric_styles=None,
          k_mode: str = "keep", apply: bool = True, run_options=None, keep_comments: bool = True,
          keep_furigana_styles: bool = False) -> BuildResult:
    src = srcmod.load(source_path)
    engine = engine or src.meta.get("engine", "stock")
    kara_effect = "kara" if engine == "0x539" else "karaoke"
    res = BuildResult(engine=engine)
    doc = AssDocument.load(lyrics_path)

    # --- fxlib modules first, then the file's own blocks
    blocks = []
    for name in src.uses:
        blocks += fxlib_source(name).blocks
    blocks += src.blocks
    default_style = src.meta.get("style")

    # --- styles added by the source: added when missing; `--@style replace` overrides the lyrics file
    for b in blocks:
        if b.kind == "style":
            replace = b.modifiers.split()[:1] == ["replace"]
            for ln in b.body.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if not ln.startswith("Style:"):
                    ln = "Style: " + ln
                st = parse_style(ln)
                st["raw"] = ln
                exists = any(s["name"] == st["name"] for s in doc.styles)
                if exists and not replace:
                    continue
                doc.styles = [s for s in doc.styles if s["name"] != st["name"]] + [st]

    # --- which lyric styles the templates read
    if lyric_styles:
        styles = list(lyric_styles)
    else:
        styles = []
        for b in blocks:
            if b.kind in ("template", "mixin") or (b.kind == "code" and b.code_class != "once"):
                st = b.options.get("style", default_style)
                if st and st not in styles:
                    styles.append(st)
        if not styles and default_style:
            styles = [default_style]
    if not styles:
        raise ValueError("cannot tell which styles are lyrics: give style= on template blocks, "
                         "--@meta style=..., or --styles")
    known = {s["name"] for s in doc.styles}
    for st in styles:
        if st not in known:
            res.warnings.append(f"style {st!r} used by the templates is not defined in the lyrics file")
    res.lyric_styles = styles

    # --- events: drop old generated lines, turn lyric lines into template input
    kept = []
    for e in doc.events:
        h = _head(e["effect"])
        if e["effect"] == "fx" or (e["comment"] and h in GENERATED_HEADS):
            continue
        is_input = e["effect"].lower() in ("karaoke", "kara")
        if not is_input and not e["comment"] and e["style"] in styles and e["effect"] == "":
            is_input = True
        if is_input:
            e = dict(e)
            e.pop("raw", None)
            e["comment"] = True
            e["effect"] = kara_effect
            e["text"], changed = ensure_k(e, k_mode)
            res.lyric_lines += 1
        kept.append(e)
    if res.lyric_lines == 0:
        res.warnings.append(f"no lyric lines found in styles {styles}")
    uses_all = any(b.kind == "template" and "all" in b.modifiers.split() for b in blocks)
    if uses_all and engine == "stock":
        others = sorted({e["style"] for e in kept if not e["comment"] and e["effect"] == "" and e["style"] not in styles})
        if others:
            res.warnings.append("templates with the `all` modifier also apply to every visible line with an empty "
                                f"Effect in other styles: {', '.join(others)}")
    needs_k = any(b.kind in ("template", "mixin") and (b.modifiers.split() or [""])[0].lower() in ("syl", "char", "furi", "word")
                  for b in blocks)
    missing_k = sum(1 for e in kept if e["effect"] == kara_effect and not re.search(r"\\[kK]", e["text"]))
    if missing_k and needs_k:
        res.warnings.append(f"{missing_k} lyric lines have no \\k tags (use --k line or --k char)")

    # --- generated lines
    gen = []
    for b in blocks:
        if b.kind == "style":
            continue
        text = srcmod.block_text(b, keep_comments)
        if b.kind == "code":
            err = check_syntax(text, f"code block at {Path(source_path).name}:{b.line}")
            if err:
                raise SyntaxError(f"Lua syntax error in code block at line {b.line}: {err}")
        style = b.options.get("style", default_style or styles[0])
        layer = int(b.options.get("layer", 0))
        gen.append({"class": "dialogue", "section": "[Events]", "comment": True, "layer": layer,
                    "start_time": 0, "end_time": 0, "style": style, "actor": b.actor,
                    "margin_l": 0, "margin_r": 0, "margin_t": 0, "effect": b.effect, "text": text,
                    "extra_ids": [], "_kind": b.kind, "_class": b.code_class})
    # keep template lines inside the first 50 dialogue lines (macro_can_template)
    first_tpl = next((i for i, g in enumerate(gen) if g["_kind"] == "template"), None)
    if first_tpl is not None and first_tpl >= 50:
        once = [g for g in gen if g["_kind"] == "code" and g["_class"] == "once"]
        rest = [g for g in gen if not (g["_kind"] == "code" and g["_class"] == "once")]
        gen = rest + once
        res.warnings.append("moved `code once` lines below the templates to keep a template within the "
                            "first 50 lines (Aegisub's Apply menu needs that)")
    for g in gen:
        g.pop("_kind")
        g.pop("_class")
    res.generated_lines = len(gen)
    doc.events = gen + kept
    res.first_template_event = next((i for i, e in enumerate(doc.events, 1) if _head(e["effect"]) == "template"), None)

    out_path = Path(output) if output else Path(lyrics_path).with_name(Path(lyrics_path).stem + "_特效.ass")
    res.output = str(out_path)
    # keep the recorded video/audio reachable from the output's folder
    moved = doc.rebase_project_paths(Path(lyrics_path).parent, out_path.parent)
    if moved:
        res.warnings.append(f"output is in another folder: rewrote {', '.join(moved)} so they still resolve")
    if apply:
        from ..aegi.templater import apply_templates
        ar = apply_templates(doc, engine, run_options, keep_furigana_styles=keep_furigana_styles)
        res.apply = ar.to_dict()
        if not ar.ok:
            doc.save(out_path)      # keep the unapplied build so the error can be inspected
            return res
    doc.save(out_path)
    return res
