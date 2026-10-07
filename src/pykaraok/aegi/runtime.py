"""One headless Automation 4 Lua state (what Aegisub creates per loaded script)."""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from lupa import luajit21

from .. import config
from ..ass import codec
from ..ass.document import AssDocument
from ..metrics import make_metrics
from . import karaoke, moon
from .vfr import START, Framerate


@dataclass
class RunOptions:
    include_dirs: list = field(default_factory=list)   # extra Lua include dirs
    font_dirs: list = field(default_factory=list)      # fonts to load for text_extents
    metrics: str = "auto"                              # auto | gdi | fonttools
    trace_level: int = 3                               # aegisub.debug.out level filter
    video_size: tuple | None = None                    # (w, h): aegisub.video_size(); None = no video loaded
    framerate: Framerate | None = None                 # frame_from_ms / ms_from_frame; None = no video
    keyframes: list | None = None
    seed: int | None = None                            # math.randomseed before the script runs
    dialog: dict | None = None                         # {"button": ..., "values": {...}} for aegisub.dialog.display
    echo_logs: bool = False                            # also print script log output to stderr


class ScriptError(RuntimeError):
    pass


def _style_to_lua(s: dict) -> dict:
    d = {k: v for k, v in s.items() if k not in ("raw", "section")}
    for k in ("color1", "color2", "color3", "color4"):
        d[k] = codec.format_style_color(s[k]) + "&"
    d["margin_b"] = s["margin_t"]
    d["relative_to"] = 2
    return d


def _style_from_lua(e: dict) -> dict:
    d = dict(e)
    for k in ("color1", "color2", "color3", "color4"):
        d[k] = codec.parse_color(d[k])
    d["section"] = "[V4+ Styles]"
    return d


class AegiRuntime:
    def __init__(self, doc: AssDocument | None = None, options: RunOptions | None = None,
                 script_path: str | Path | None = None):
        self.opts = options or RunOptions()
        self.doc = doc
        self.logs: list[tuple[int, str]] = []
        self.progress: dict[str, object] = {}
        self.metrics = make_metrics(self.opts.metrics, self.opts.font_dirs)
        self.include_dirs = [str(p).replace("\\", "/") for p in config.default_include_dirs(self.opts.include_dirs)]
        self.script_dir = str(Path(script_path).parent if script_path else Path.cwd()).replace("\\", "/")
        self.lua = luajit21.LuaRuntime(unpack_returned_tuples=True, encoding="utf-8",
                                       register_eval=False, register_builtins=False)
        self.api = self._install()
        if self.opts.seed is not None:
            self.lua.execute(f"math.randomseed({int(self.opts.seed)})")
        if doc is not None:
            self.load_document(doc)

    # ------------------------------------------------------------- services
    def _py(self) -> dict:
        lua = self.lua
        opts = self.opts
        doc = self.doc

        def load_source(path):
            data = Path(path).read_bytes()
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            text = data.decode("utf-8")
            if str(path).lower().endswith(".moon"):
                return moon.compile_cached(text, str(path))
            return text

        def text_extents(fontname, fontsize, bold, italic, underline, strikeout, encoding,
                         spacing, scale_x, scale_y, text):
            return self.metrics.text_extents({
                "fontname": fontname, "fontsize": fontsize, "bold": bold, "italic": italic,
                "underline": underline, "strikeout": strikeout, "encoding": encoding,
                "spacing": spacing, "scale_x": scale_x, "scale_y": scale_y}, text)

        def parse_kara(text, start_ms):
            return lua.table_from(karaoke.parse_karaoke_data(text, int(start_ms)), recursive=True)

        def log(level, msg):
            self.logs.append((int(level), msg))
            if opts.echo_logs:
                import sys
                sys.stderr.write(msg if msg.endswith("\n") else msg + "\n")

        def progress(kind, value):
            self.progress[kind] = value

        def case(kind, s):
            return {"upper": s.upper(), "lower": s.lower(), "fold": s.casefold()}[kind]

        def frame_from_ms(ms):
            return opts.framerate.frame_at_time(int(ms), START) if opts.framerate else None

        def ms_from_frame(frame):
            return opts.framerate.time_at_frame(int(frame), START) if opts.framerate else None

        def decode_path(p):
            base = {
                "?script": self.script_dir,
                "?data": str(config.AEGISUB_VENDOR),
                "?user": str(config.cache_dir() / "user"),
                "?local": str(config.cache_dir() / "local"),
                "?temp": tempfile.gettempdir(),
                "?dictionary": str(config.cache_dir() / "dictionaries"),
            }
            if doc is not None:
                for key, prop in (("?audio", "Audio File"), ("?video", "Video File")):
                    v = doc.project_property(prop)
                    if v:
                        base[key] = str(Path(self.script_dir) / Path(v).parent)
            for k, v in base.items():
                if p.startswith(k):
                    return v.replace("\\", "/") + p[len(k):]
            return p

        def dialog(kind, dlg=None, buttons=None, ids=None):
            resp = opts.dialog or {}
            if kind != "display":
                return resp.get(kind)
            values = resp.get("values", {})
            results = {}
            if dlg is not None:
                for item in dlg.values():
                    name = item["name"] if item["name"] is not None else None
                    if not name:
                        continue
                    if name in values:
                        results[name] = values[name]
                        continue
                    cls = (item["class"] or "").lower()
                    if cls in ("edit", "textbox"):
                        results[name] = item["text"] or ""
                    else:
                        results[name] = item["value"]
            button = resp.get("button")
            if button is None:
                button = buttons[1] if buttons is not None and buttons[1] is not None else True
            return button, lua.table_from(results)

        def compile_moon(src, name):
            return moon.compile_cached(src, str(name))

        def re_impl():
            from .re_impl import make_re_impl
            return make_re_impl(lua)

        video = None
        if opts.video_size:
            w, h = opts.video_size
            video = lua.table_from([int(w), int(h), w / h, 0])
        project = {}
        if doc is not None:
            for key, prop in (("audio_file", "Audio File"), ("video_file", "Video File"),
                              ("timecodes_file", "Timecodes File"), ("keyframes_file", "Keyframes File")):
                project[key] = doc.project_property(prop) or ""
        res_x, res_y = doc.resolution() if doc is not None else (384, 288)

        return {
            "load_source": load_source,
            "file_exists": lambda p: os.path.isfile(p),
            "text_extents": text_extents,
            "parse_kara": parse_kara,
            "log": log,
            "progress": progress,
            "case": case,
            "frame_from_ms": frame_from_ms,
            "ms_from_frame": ms_from_frame,
            "decode_path": decode_path,
            "dialog": dialog,
            "compile_moon": compile_moon,
            "re_impl": re_impl,
            "include_dirs": lua.table_from(self.include_dirs),
            "script_dir": self.script_dir,
            "trace_level": int(opts.trace_level),
            "file_name": doc.path.name if doc is not None and doc.path else None,
            "video": video,
            "keyframes": lua.table_from(opts.keyframes) if opts.keyframes else None,
            "project": lua.table_from(project),
            "res_x": res_x,
            "res_y": res_y,
            "monkeypatch": str(config.AEGISUB_INCLUDE / "unicode-monkeypatch.lua").replace("\\", "/"),
        }

    def _install(self):
        src = (config.LUA_DIR / "prelude.lua").read_text(encoding="utf-8")
        loader = self.lua.eval("function(src) return assert(loadstring(src, '@pykaraok/prelude.lua')) end")
        py = self.lua.table_from(self._py())
        return loader(src)(py)

    # --------------------------------------------------------------- lines
    def load_document(self, doc: AssDocument) -> None:
        lua = self.lua
        self.api.set_extradata(lua.table_from([{"id": e.id, "key": e.key, "value": e.value} for e in doc.extradata],
                                              recursive=True), doc.next_extradata_id)
        entries = []
        for e in doc.info:
            entries.append({"class": "info", "key": e["key"], "value": e["value"]})
        for s in doc.styles:
            entries.append(_style_to_lua(s))
        for ev in doc.events:
            d = {k: v for k, v in ev.items() if k not in ("raw", "extra_ids", "section")}
            d["margin_b"] = ev["margin_t"]
            d["_ids"] = list(ev.get("extra_ids") or [])
            entries.append(d)
        self.api.add_entries(lua.table_from(entries, recursive=True))

    def entries(self) -> list[dict]:
        out = []
        tbl = self.api.get_entries()
        for i in range(1, len(tbl) + 1):
            t = tbl[i]
            d = dict(t.items())
            cls = d.get("class")
            if cls == "dialogue":
                ids = d.pop("ids", None)
                d["extra_ids"] = [int(ids[k]) for k in range(1, len(ids) + 1)] if ids is not None else []
                d["section"] = "[Events]"
            elif cls == "style":
                d = _style_from_lua(d)
            out.append(d)
        return out

    def extradata(self) -> tuple[list[tuple[int, str, str]], int]:
        lst, next_id = self.api.get_extradata()
        out = []
        for i in range(1, len(lst) + 1):
            e = lst[i]
            out.append((int(e["id"]), e["key"], e["value"]))
        return out, int(next_id)

    def commit_to(self, doc: AssDocument) -> None:
        """Write the subtitle object's lines back into the document (what Aegisub's commit does)."""
        doc.set_entries(self.entries())
        lst, next_id = self.extradata()
        old = {e.id: e for e in doc.extradata}
        from ..ass.document import ExtradataEntry
        new = []
        for eid, key, value in lst:
            prev = old.get(eid)
            raw = prev.raw if prev is not None and prev.key == key and prev.value == value else None
            new.append(ExtradataEntry(eid, key, value, raw))
        doc.extradata = new
        doc.next_extradata_id = next_id

    # ------------------------------------------------------------- scripts
    def load_script(self, path: str | Path) -> None:
        path = str(Path(path)).replace("\\", "/")
        ok, err = self.api.load_script(path)
        if not ok:
            raise ScriptError(f"failed to load {path}:\n{err}")

    def macro_names(self) -> list[str]:
        t = self.api.macro_names()
        return [t[i] for i in range(1, len(t) + 1)]

    def validate_macro(self, name: str) -> tuple[bool, str]:
        res = self.api.validate_macro(name)
        if isinstance(res, tuple):
            return bool(res[0]), str(res[1] or "")
        return bool(res), ""

    def run_macro(self, name: str, selected: list[int] | None = None, active: int = 0) -> tuple[str, str, float]:
        t0 = time.perf_counter()
        sel = self.lua.table_from(selected or [])
        status, msg = self.api.run_macro(name, sel, active)
        return status, msg, time.perf_counter() - t0

    def run_filter(self, name: str) -> tuple[str, str, float]:
        t0 = time.perf_counter()
        status, msg = self.api.run_filter(name, self.lua.table())
        return status, msg, time.perf_counter() - t0
