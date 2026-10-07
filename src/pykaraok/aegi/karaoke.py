"""aegisub.parse_karaoke_data, ported from Aegisub.

Sources (TypesettingTools/Aegisub @ 06d5f4b9):
  src/ass_karaoke.cpp            ParseKaraokeSyllables
  src/ass_dialogue.cpp           AssDialogue::ParseTags (block splitting, \\p drawings)
  src/ass_override.cpp           AssDialogueBlockOverride::ParseTags (paren-aware tag split)
  libaegisub/ass/karaoke.cpp     KaraokeSyllable::GetText
  src/auto4_lua_assfile.cpp      LuaParseKaraokeData (index 0 placeholder, relative times)

Differences from Aegisub that cannot matter for karaoke templates: tag text is
copied verbatim instead of being re-serialised from parsed parameters.
"""
from __future__ import annotations

import re

_INT = re.compile(r"\s*([+-]?\d+)")
# Karaoke tags in the order of Aegisub's prototype table (ass_override.cpp).
# Matching is a case-sensitive prefix test, so "\kt50" matches "\k" with the
# parameter "t50" (duration 0), exactly like Aegisub.
_KTAGS = ("\\ko", "\\kf", "\\k", "\\K")


def _atoi(s: str) -> int:
    m = _INT.match(s)
    return int(m.group(1)) if m else 0


def _match_ktag(tag: str) -> tuple[str, str] | None:
    for name in _KTAGS:
        if tag.startswith(name):
            return name, tag[len(name):]
    return None


def split_override(inner: str) -> list[str]:
    """AssDialogueBlockOverride::ParseTags: split at backslashes outside parentheses."""
    tags = []
    depth = 0
    start = 0
    for i in range(1, len(inner)):
        c = inner[i]
        if depth > 0:
            if c == ")":
                depth -= 1
        elif c == "\\":
            tags.append(inner[start:i])
            start = i
        elif c == "(":
            depth += 1
    if inner:
        tags.append(inner[start:])
    return tags


def parse_blocks(text: str) -> list[tuple[str, str]]:
    """AssDialogue::ParseTags. Returns (kind, text) with kind in plain/comment/override/drawing.

    For override blocks the text is the block content without braces; for
    comment blocks it is the full ``{...}``.
    """
    blocks: list[tuple[str, str]] = []
    if text == "":
        return [("plain", "")]
    drawing = 0
    cur = 0
    n = len(text)
    while cur < n:
        if text[cur] == "{":
            end = text.find("}", cur)
            if end != -1:
                work = text[cur + 1:end]
                cur = end + 1
                if work and "\\" not in work:
                    blocks.append(("comment", "{" + work + "}"))
                else:
                    blocks.append(("override", work))
                    for tag in split_override(work):
                        if tag.startswith("\\p") and not tag.startswith("\\pos") and not tag.startswith("\\pbo"):
                            drawing = _atoi(tag[2:])
                continue
        # plain text or drawing up to the next '{'
        end = text.find("{", cur + 1)
        if end == -1:
            work, cur = text[cur:], n
        else:
            work, cur = text[cur:end], end
        blocks.append(("drawing" if drawing else "plain", work))
    return blocks


class _Syl:
    __slots__ = ("start_time", "duration", "tag_type", "text", "ovr")

    def __init__(self, start_time: int):
        self.start_time = start_time
        self.duration = 0
        self.tag_type = "\\k"
        self.text = ""
        self.ovr: dict[int, str] = {}

    def add_ovr(self, s: str):
        pos = len(self.text.encode("utf-8"))
        self.ovr[pos] = self.ovr.get(pos, "") + s

    def get_text(self) -> str:
        raw = self.text.encode("utf-8")
        out = bytearray()
        idx = 0
        for pos in sorted(self.ovr):
            out += raw[idx:pos]
            out += self.ovr[pos].encode("utf-8")
            idx = pos
        out += raw[idx:]
        return out.decode("utf-8", "replace")


def parse_syllables(text: str, line_start: int = 0) -> list[dict]:
    """ParseKaraokeSyllables. Times are absolute (line_start based)."""
    syls: list[_Syl] = []
    syl = _Syl(line_start)
    for kind, body in parse_blocks(text):
        if kind == "plain":
            syl.text += body
        elif kind in ("comment", "drawing"):
            syl.add_ovr(body)
        else:
            in_tag = False
            for tag in split_override(body):
                m = _match_ktag(tag)
                if m:
                    if in_tag:
                        syl.add_ovr("}")
                        in_tag = False
                    name, param = m
                    if name == "\\K":
                        name = "\\kf"
                    if syl.duration > 0 or syl.text != "":
                        syls.append(syl)
                        nxt = _Syl(syl.start_time)
                        nxt.duration = syl.duration
                        nxt.tag_type = syl.tag_type
                        syl = nxt
                    syl.tag_type = name
                    syl.start_time += syl.duration
                    param = param.strip()
                    if param.startswith("("):
                        param = param[1:]
                    syl.duration = _atoi(param) * 10
                else:
                    if not in_tag:
                        syl.add_ovr("{")
                    in_tag = True
                    syl.add_ovr(tag)
            if in_tag:
                syl.add_ovr("}")
    syls.append(syl)
    return [{"start_time": s.start_time, "duration": s.duration, "tag": s.tag_type,
             "text": s.get_text(), "text_stripped": s.text} for s in syls]


def parse_karaoke_data(text: str, line_start: int) -> list[dict]:
    """LuaParseKaraokeData: element 0 is an empty placeholder, times are relative to the line."""
    out = [{"duration": 0, "start_time": 0, "end_time": 0, "tag": "", "text": "", "text_stripped": ""}]
    for s in parse_syllables(text, line_start):
        out.append({
            "duration": s["duration"],
            "start_time": s["start_time"] - line_start,
            "end_time": s["start_time"] + s["duration"] - line_start,
            "tag": s["tag"],
            "text": s["text"],
            "text_stripped": s["text_stripped"],
        })
    return out
