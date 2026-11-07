r"""Template source files: Lua-looking text files that build into kara-templater lines.

Format (one block per directive; the block body runs until the next directive):

    --@meta engine=stock style=JP          defaults for the whole file
    --@use core shapes                     embed pykaraok fxlib modules as `code once` lines
    --@note 说明文字                        a Comment line with Effect "note" (ignored by templaters)
    --@code once | 配置                     Lua code; "| text" goes into the Actor column
    COL = {ice = '&HFFDCC9&'}
    --@template syl noblank style=JP layer=2 | 冰晶本体
    !rt_in()!{\an5\move(...)}
    --@mixin ...                           (0x539 engine)
    --@style Style: Spark,Arial,20,...       add a style the lyrics file lacks
    --@style replace Style: JP,Arial,48,...  replace the lyrics file's style of that name

Code blocks are flattened to one line (comments kept as --[[ ]]).  Template
blocks are joined line by line with leading indentation removed; lines that
start with "--" inside a template block are comments.

Everything else (backslashes, quotes) is written exactly as in the file, so
template text never has to pass through a shell.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .luaflat import FlattenError, flatten

_DIRECTIVE = re.compile(r"^--@(\w+)\b(.*)$")
KINDS = ("meta", "use", "note", "code", "template", "mixin", "style")


@dataclass
class Block:
    kind: str                       # note | code | template | mixin | style
    modifiers: str = ""             # e.g. "once", "syl noblank"
    options: dict = field(default_factory=dict)   # style, layer, actor, start, end
    actor: str = ""
    body: str = ""
    line: int = 0                   # line number of the directive in the source

    @property
    def effect(self) -> str:
        if self.kind == "note":
            return "note"
        return (self.kind + " " + self.modifiers).strip()

    @property
    def code_class(self) -> str:
        return self.modifiers.split()[0].lower() if self.modifiers.split() else ""


@dataclass
class Source:
    path: Path | None
    meta: dict = field(default_factory=dict)
    uses: list[str] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)


def _split_head(rest: str) -> tuple[str, dict, str]:
    rest = rest.strip()
    actor = ""
    if "|" in rest:
        rest, actor = rest.split("|", 1)
        actor = actor.strip()
    mods, opts = [], {}
    for tok in shlex.split(rest, posix=True) if rest else []:
        if "=" in tok and re.match(r"^[a-z_]+=", tok):
            k, v = tok.split("=", 1)
            opts[k] = v
        else:
            mods.append(tok)
    return " ".join(mods), opts, actor


def parse(text: str, path: Path | None = None) -> Source:
    src = Source(path)
    cur: Block | None = None
    body: list[str] = []

    def close():
        nonlocal cur, body
        if cur is not None:
            cur.body = "\n".join(body).strip("\n")
            src.blocks.append(cur)
        cur, body = None, []

    # not str.splitlines(): it also breaks at U+2028, form feed and others, which template text can contain
    for no, ln in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        m = _DIRECTIVE.match(ln)
        if m and m.group(1) in KINDS:
            kind, rest = m.group(1), m.group(2)
            if kind == "meta":
                close()
                _, opts, _ = _split_head(rest)
                src.meta.update(opts)
                continue
            if kind == "use":
                close()
                src.uses += [u for u in re.split(r"[\s,]+", rest.strip()) if u]
                continue
            close()
            if kind == "note":
                cur = Block("note", "", {}, "", "", no)
                body = [rest.strip()] if rest.strip() else []
                continue
            if kind == "style":
                r = rest.strip()
                mods = ""
                if r.split()[:1] == ["replace"]:
                    mods, r = "replace", r[len("replace"):].strip()
                cur = Block("style", mods, {}, "", "", no)
                body = [r] if r else []
                continue
            mods, opts, actor = _split_head(rest)
            cur = Block(kind, mods, opts, actor or opts.get("actor", ""), "", no)
            continue
        if cur is not None:
            body.append(ln)
    close()
    return src


def load(path: str | Path) -> Source:
    path = Path(path)
    return parse(path.read_text(encoding="utf-8-sig"), path)


def block_text(b: Block, keep_comments: bool = True) -> str:
    """The event text for a block."""
    if b.kind == "code":
        try:
            return flatten(b.body, keep_comments)
        except FlattenError as exc:
            raise FlattenError(f"block at line {b.line}: {exc}") from None
    if b.kind in ("template", "mixin"):
        # only ASCII blanks are indentation: a full-width space is template text
        parts = []
        for ln in b.body.split("\n"):
            s = ln.strip(" \t\r")
            if not s or s.startswith("--"):
                continue
            parts.append(ln.lstrip(" \t").rstrip("\r"))
        return "".join(parts)
    return " ".join(b.body.split())


# ---------------------------------------------------------------- extract

def extract_from_events(events: list[dict], default_style: str | None = None, styles_raw: dict | None = None) -> str:
    """Write the template/code/mixin/note lines of a subtitle file as a source file.

    styles_raw: style name -> "Style: ..." line; styles used by the templates are written as
    `--@style` blocks (added at build time only when the lyrics file lacks them).
    """
    lines = ["-- pykaraok template source, extracted from an existing file",
             "-- build: pykaraok build THIS_FILE --lyrics LYRICS.ass -o OUT.ass", ""]
    styles = [e["style"] for e in events if _head(e["effect"]) in ("template", "code", "mixin")]
    common = max(set(styles), key=styles.count) if styles else default_style
    if common:
        lines += [f"--@meta style={_q(common)}", ""]
    if styles_raw:
        used = []
        for e in events:
            if _head(e["effect"]) in ("template", "code", "mixin") and e["style"] not in used:
                used.append(e["style"])
            for m in re.findall(r"restyle\(\s*[\"']([^\"']+)", e["text"]):
                if m not in used:
                    used.append(m)
        for name in used:
            if name in styles_raw:
                lines.append("--@style " + styles_raw[name])
        if used:
            lines.append("")
    for e in events:
        head = _head(e["effect"])
        # zero-length comment lines with an empty Effect are the usual place for explanations
        if head == "" and e["comment"] and e["start_time"] == 0 and e["end_time"] == 0 and e["text"].strip():
            head = "note"
        if head not in ("template", "code", "mixin", "note"):
            continue
        if head == "note":
            lines.append("--@note " + e["text"])
            lines.append("")
            continue
        mods = e["effect"].strip()[len(head):].strip()
        opts = []
        if e["style"] != common:
            opts.append(f"style={_q(e['style'])}")
        if int(e["layer"]) != 0:
            opts.append(f"layer={int(e['layer'])}")
        tail = f" | {e['actor']}" if e["actor"] else ""
        lines.append(f"--@{head} {mods}{(' ' + ' '.join(opts)) if opts else ''}{tail}".rstrip())
        lines.append(e["text"])
        lines.append("")
    return "\n".join(lines)


def _head(effect: str) -> str:
    return effect.strip().split(" ")[0].lower() if effect.strip() else ""


def _q(v: str) -> str:
    return shlex.quote(v) if re.search(r"\s|['\"]", v) else v
