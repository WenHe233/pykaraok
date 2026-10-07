"""ASS file model that mirrors what Aegisub hands to automation scripts.

Parsing and serialisation follow Aegisub's own code (src/ass_parser.cpp,
src/ass_dialogue.cpp, src/ass_style.cpp, src/ass_file.cpp).  Unlike Aegisub we
keep everything we do not need to touch byte for byte: comment lines, unknown
sections, [Aegisub Project Garbage], fonts/graphics, the BOM and the newline
style.  Lines that the script did not change are written back verbatim.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import codec

# Keys that Aegisub moves out of [Script Info] into project properties
# (src/ass_parser.cpp HeaderToProperty); they never reach automation scripts.
_PROPERTY_KEYS = {
    "Automation Scripts", "Export Filters", "Export Encoding", "Last Style Storage",
    "Audio URI", "Audio File", "Video File", "Timecodes File", "Keyframes File",
    "Video Zoom Percent", "Scroll Position", "Active Line", "Video Position",
    "Video AR Mode", "Video AR Value", "Aegisub Video Zoom Percent",
    "Aegisub Scroll Position", "Aegisub Active Line", "Aegisub Video Position",
}

STYLE_FORMAT = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
                "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
                "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
EVENT_FORMAT = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"

_EXTRA_PREFIX = re.compile(r"^\{(=\d+)+\}")
_EXTRA_LINE = re.compile(r"^Data:\s*(\d+),([^,]+),(.)(.*)$")


@dataclass
class Section:
    name: str            # header text without brackets, original case
    header: str          # raw header line
    lines: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.name.lower()


@dataclass
class ExtradataEntry:
    id: int
    key: str
    value: str
    raw: str | None = None   # original line, reused when writing back


def parse_style(raw: str) -> dict:
    body = raw.split(":", 1)[1] if ":" in raw else raw
    p = [t.strip() for t in body.split(",")]
    if len(p) != 23:
        raise ValueError(f"malformed style (expected 23 fields, got {len(p)}): {raw}")

    def num(s):
        try:
            return float(s)
        except ValueError:
            return 0.0

    def integer(s):
        try:
            return int(float(s))
        except ValueError:
            return 0

    return {
        "class": "style", "section": "[V4+ Styles]",
        "name": p[0], "fontname": p[1], "fontsize": num(p[2]),
        "color1": codec.parse_color(p[3]), "color2": codec.parse_color(p[4]),
        "color3": codec.parse_color(p[5]), "color4": codec.parse_color(p[6]),
        "bold": integer(p[7]) != 0, "italic": integer(p[8]) != 0,
        "underline": integer(p[9]) != 0, "strikeout": integer(p[10]) != 0,
        "scale_x": num(p[11]), "scale_y": num(p[12]), "spacing": num(p[13]), "angle": num(p[14]),
        "borderstyle": integer(p[15]), "outline": num(p[16]), "shadow": num(p[17]),
        "align": integer(p[18]), "margin_l": integer(p[19]), "margin_r": integer(p[20]),
        "margin_t": integer(p[21]), "encoding": integer(p[22]),
    }


def format_style(s: dict) -> str:
    name = s["name"].replace(",", ";")
    font = s["fontname"].replace(",", ";")
    g = codec.fmt_g
    return "Style: " + ",".join([
        name, font, g(s["fontsize"]),
        codec.format_style_color(s["color1"]), codec.format_style_color(s["color2"]),
        codec.format_style_color(s["color3"]), codec.format_style_color(s["color4"]),
        "-1" if s["bold"] else "0", "-1" if s["italic"] else "0",
        "-1" if s["underline"] else "0", "-1" if s["strikeout"] else "0",
        g(s["scale_x"]), g(s["scale_y"]), g(s["spacing"]), g(s["angle"]),
        str(int(s["borderstyle"])), g(s["outline"]), g(s["shadow"]), str(int(s["align"])),
        str(int(s["margin_l"])), str(int(s["margin_r"])), str(int(s["margin_t"])), str(int(s["encoding"])),
    ])


def parse_event(raw: str) -> dict:
    if raw.startswith("Dialogue:"):
        comment, rest = False, raw[10:]
    elif raw.startswith("Comment:"):
        comment, rest = True, raw[9:]
    else:
        raise ValueError(f"not an event line: {raw}")
    parts = rest.split(",", 9)
    if len(parts) < 10:
        raise ValueError(f"malformed event line: {raw}")
    first = parts[0].strip()
    layer = 0 if first.lower().startswith("marked=") else int(first)

    def margin(tok):
        try:
            v = int(tok.strip())
        except ValueError:
            v = 0
        return max(-9999, min(v, 99999))

    text = parts[9]
    ids: list[int] = []
    if text.startswith("{="):
        m = _EXTRA_PREFIX.match(text)
        if m:
            ids = [int(x) for x in re.findall(r"=(\d+)", m.group(0))]
            text = text[m.end():]
    return {
        "class": "dialogue", "section": "[Events]", "comment": comment, "layer": layer,
        "start_time": codec.parse_time(parts[1].strip()), "end_time": codec.parse_time(parts[2].strip()),
        "style": parts[3].strip(), "actor": parts[4].strip(),
        "margin_l": margin(parts[5]), "margin_r": margin(parts[6]), "margin_t": margin(parts[7]),
        "effect": parts[8].strip(), "text": text, "extra_ids": ids,
    }


def format_event(e: dict) -> str:
    """AssDialogue::GetEntryData."""
    def unsafe(s):
        return s.replace(",", ";")
    out = ["Comment: " if e["comment"] else "Dialogue: "]
    out.append(f"{int(e['layer'])},{codec.format_time(e['start_time'])},{codec.format_time(e['end_time'])},")
    out.append(f"{unsafe(e['style'])},{unsafe(e['actor'])},")
    out.append(f"{int(e['margin_l'])},{int(e['margin_r'])},{int(e['margin_t'])},")
    out.append(unsafe(e["effect"]) + ",")
    ids = e.get("extra_ids") or []
    if ids:
        out.append("{" + "".join(f"={i}" for i in ids) + "}")
    out.append(e["text"].replace("\n", "").replace("\r", ""))
    return "".join(out)


def _event_key(e: dict) -> tuple:
    return (bool(e["comment"]), int(e["layer"]), codec.round_cs(codec.clamp_time(e["start_time"])),
            codec.round_cs(codec.clamp_time(e["end_time"])), e["style"], e["actor"],
            int(e["margin_l"]), int(e["margin_r"]), int(e["margin_t"]), e["effect"], e["text"],
            tuple(e.get("extra_ids") or ()))


def _style_key(s: dict) -> tuple:
    return tuple((k, s[k]) for k in sorted(s) if k not in ("raw", "section", "class"))


class AssDocument:
    def __init__(self):
        self.path: Path | None = None
        self.bom = True
        self.newline = "\r\n"
        self.trailing_newline = True
        self.sections: list[Section] = []
        self.info: list[dict] = []
        self.styles: list[dict] = []
        self.events: list[dict] = []
        self.extradata: list[ExtradataEntry] = []
        self.next_extradata_id = 0
        self._orig_info: list[tuple[str, str]] = []

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, path: str | Path) -> "AssDocument":
        path = Path(path)
        doc = cls.from_bytes(path.read_bytes())
        doc.path = path
        return doc

    @classmethod
    def from_text(cls, text: str) -> "AssDocument":
        return cls.from_bytes(text.encode("utf-8"))

    @classmethod
    def from_bytes(cls, data: bytes) -> "AssDocument":
        doc = cls()
        doc.bom = data.startswith(b"\xef\xbb\xbf")
        if doc.bom:
            data = data[3:]
        text = data.decode("utf-8")
        doc.newline = "\r\n" if "\r\n" in text else "\n"
        doc.trailing_newline = text.endswith("\n")
        lines = text.splitlines()
        cur: Section | None = None
        for ln in lines:
            s = ln.strip()
            if s.startswith("[") and s.endswith("]") and not (cur and cur.key in ("fonts", "graphics") and _looks_like_attachment(s)):
                cur = Section(s[1:-1], ln)
                doc.sections.append(cur)
                continue
            if cur is None:
                cur = Section("", "")
                doc.sections.append(cur)
            cur.lines.append(ln)
        doc._parse_sections()
        return doc

    def _parse_sections(self):
        for sec in self.sections:
            k = sec.key
            if k == "script info":
                for ln in sec.lines:
                    if ln.startswith(";") or ln.startswith("Collisions:"):
                        continue
                    pos = ln.find(":")
                    if pos < 0:
                        continue
                    key, value = ln[:pos], ln[pos + 1:].lstrip()
                    if key in _PROPERTY_KEYS or key.startswith("Automation Settings "):
                        continue
                    self.info.append({"class": "info", "section": "[Script Info]", "key": key, "value": value})
            elif k in ("v4+ styles", "v4 styles"):
                for ln in sec.lines:
                    if ln.startswith("Style:"):
                        st = parse_style(ln)
                        st["raw"] = ln
                        self.styles.append(st)
            elif k == "events":
                for ln in sec.lines:
                    if ln.startswith("Dialogue:") or ln.startswith("Comment:"):
                        ev = parse_event(ln)
                        ev["raw"] = ln
                        self.events.append(ev)
            elif k == "aegisub extradata":
                for ln in sec.lines:
                    m = _EXTRA_LINE.match(ln.replace("\0", "�"))
                    if not m:
                        continue
                    eid = int(m.group(1))
                    key = codec.inline_string_decode(m.group(2))
                    kind, value = m.group(3), m.group(4)
                    if kind == "e":
                        value = codec.inline_string_decode(value)
                    elif kind == "u":
                        value = codec.uudecode(value).decode("utf-8", "replace")
                    else:
                        value = ""
                    self.next_extradata_id = max(self.next_extradata_id, eid + 1)
                    self.extradata.append(ExtradataEntry(eid, key, value, ln))
        self._orig_info = [(i["key"], i["value"]) for i in self.info]

    # ------------------------------------------------------------ properties
    def info_value(self, key: str, default: str | None = None) -> str | None:
        for i in self.info:
            if i["key"].lower() == key.lower():
                return i["value"]
        return default

    def resolution(self) -> tuple[int, int]:
        """Script resolution as Aegisub's AssFile::GetResolution computes it."""
        def num(k):
            try:
                return int(float(self.info_value(k, "0") or 0))
            except ValueError:
                return 0
        w, h = num("PlayResX"), num("PlayResY")
        if w == 0 and h == 0:
            return 384, 288
        if w == 0:
            w = 1280 if h == 1024 else h * 4 // 3
        if h == 0:
            h = 1024 if w == 1280 else w * 3 // 4
        return w, h

    def project_property(self, key: str) -> str | None:
        for sec in self.sections:
            if sec.key in ("aegisub project garbage", "script info"):
                for ln in sec.lines:
                    if ln.startswith(key + ":"):
                        return ln[len(key) + 1:].strip()
        return None

    def rebase_project_paths(self, old_dir: str | Path, new_dir: str | Path) -> list[str]:
        """Rewrite relative Video/Audio/Timecodes/Keyframes paths so they still resolve when
        the file is saved in new_dir instead of old_dir.  Returns the keys that changed."""
        import os
        old_dir, new_dir = Path(old_dir).resolve(), Path(new_dir).resolve()
        if old_dir == new_dir:
            return []
        changed = []
        keys = ("Audio File", "Video File", "Timecodes File", "Keyframes File", "Audio URI")
        for sec in self.sections:
            if sec.key not in ("aegisub project garbage", "script info"):
                continue
            for i, ln in enumerate(sec.lines):
                for k in keys:
                    if not ln.startswith(k + ":"):
                        continue
                    v = ln[len(k) + 1:].strip()
                    if not v or v.startswith("?") or Path(v).is_absolute():
                        continue
                    target = (old_dir / v).resolve()
                    if not target.exists():
                        continue
                    try:
                        nv = os.path.relpath(target, new_dir)
                    except ValueError:          # different drive on Windows
                        nv = str(target)
                    sec.lines[i] = f"{k}: {nv}"
                    changed.append(k)
        return changed

    def style(self, name: str) -> dict | None:
        for s in self.styles:
            if s["name"] == name:
                return s
        return None

    def extra_for(self, ids) -> dict[str, str]:
        """AssFile::GetExtradata as a key -> value dict."""
        by_id = {e.id: e for e in self.extradata}
        out = {}
        for i in sorted(ids):
            e = by_id.get(i)
            if e is not None:
                out[e.key] = e.value
        return out

    def add_extradata(self, key: str, value: str) -> int:
        """AssFile::AddExtradata (dedups by exact key and value)."""
        for e in self.extradata:
            if e.key == key and e.value == value:
                return e.id
        eid = self.next_extradata_id
        self.extradata.append(ExtradataEntry(eid, key, value, None))
        self.next_extradata_id += 1
        return eid

    # --------------------------------------------------------------- entries
    def entries(self) -> list[dict]:
        """Lines in the order Aegisub's subtitle object exposes them: info, styles, events."""
        return [copy.deepcopy(x) for x in self.info + self.styles + self.events]

    def set_entries(self, entries: list[dict]) -> None:
        """Replace info/styles/events with what a script left in the subtitle object."""
        info, styles, events = [], [], []
        orig_styles = {(s["name"], _style_key(s)): s.get("raw") for s in self.styles}
        orig_events: dict[tuple, list[str]] = {}
        for e in self.events:
            orig_events.setdefault(_event_key(e), []).append(e.get("raw"))
        for e in entries:
            cls = e.get("class")
            if cls == "info":
                info.append({"class": "info", "section": "[Script Info]", "key": e["key"], "value": e["value"]})
            elif cls == "style":
                st = {k: v for k, v in e.items() if k != "raw"}
                raw = orig_styles.get((st["name"], _style_key(st)))
                if raw:
                    st["raw"] = raw
                styles.append(st)
            elif cls == "dialogue":
                ev = {k: v for k, v in e.items() if k != "raw"}
                raws = orig_events.get(_event_key(ev))
                if raws:
                    ev["raw"] = raws.pop(0)
                events.append(ev)
        self.info, self.styles, self.events = info, styles, events

    # ------------------------------------------------------------------ save
    def _clean_extradata(self):
        """AssFile::CleanExtradata: one id per key per line, drop unused entries."""
        if not self.extradata:
            return
        by_id = {e.id: e for e in self.extradata}
        used = set()
        for ev in self.events:
            ids = ev.get("extra_ids") or []
            if not ids:
                continue
            keys: dict[str, int] = {}
            for i in sorted(ids):
                if i in by_id:
                    keys[by_id[i].key] = i
            used.update(keys.values())
            if len(keys) != len(ids):
                ev["extra_ids"] = sorted(keys.values())
                ev.pop("raw", None)
        self.extradata = [e for e in self.extradata if e.id in used]

    def to_text(self) -> str:
        self._clean_extradata()
        out: list[str] = []
        wrote_extradata = False
        info_changed = [(i["key"], i["value"]) for i in self.info] != self._orig_info
        for sec in self.sections:
            k = sec.key
            if sec.header:
                out.append(sec.header)
            if k == "script info" and info_changed:
                out.extend(ln for ln in sec.lines if ln.startswith(";"))
                out.extend(f"{i['key']}: {i['value']}" for i in self.info)
                out.append("")
            elif k in ("v4+ styles", "v4 styles"):
                fmt = next((ln for ln in sec.lines if ln.startswith("Format:")), STYLE_FORMAT)
                out.append(fmt)
                out.extend(s.get("raw") or format_style(s) for s in self.styles)
                out.append("")
            elif k == "events":
                fmt = next((ln for ln in sec.lines if ln.startswith("Format:")), EVENT_FORMAT)
                out.append(fmt)
                out.extend(e.get("raw") or format_event(e) for e in self.events)
                out.append("")
            elif k == "aegisub extradata":
                wrote_extradata = True
                out.extend(self._extradata_lines())
                out.append("")
            else:
                out.extend(sec.lines)
        if not wrote_extradata and self.extradata:
            out.append("[Aegisub Extradata]")
            out.extend(self._extradata_lines())
            out.append("")
        # collapse the blank line we add at the end of rebuilt sections when
        # the original already ended with one
        text = self.newline.join(_dedupe_blank_runs(out))
        if self.trailing_newline and not text.endswith(self.newline):
            text += self.newline
        return text

    def _extradata_lines(self) -> list[str]:
        lines = []
        for e in self.extradata:
            if e.raw is not None:
                lines.append(e.raw)
            else:
                lines.append(f"Data: {e.id},{codec.inline_string_encode(e.key)},{codec.encode_extradata_value(e.value)}")
        return lines

    def to_bytes(self) -> bytes:
        data = self.to_text().encode("utf-8")
        return (b"\xef\xbb\xbf" + data) if self.bom else data

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.to_bytes())


_KNOWN_SECTIONS = {"script info", "v4+ styles", "v4 styles", "events", "fonts", "graphics",
                   "aegisub project garbage", "aegisub extradata"}


def _looks_like_attachment(s: str) -> bool:
    """Inside [Fonts]/[Graphics] a uuencoded data line may look like '[...]'."""
    return s[1:-1].lower() not in _KNOWN_SECTIONS


def _dedupe_blank_runs(lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in lines:
        if ln == "" and out and out[-1] == "":
            continue
        out.append(ln)
    while out and out[-1] == "":
        out.pop()
    return out
