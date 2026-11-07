"""Turn multi-line Lua into the single line an ASS event can hold.

kara-templater reads `code` lines from the event text, which cannot contain
newlines.  Line comments become block comments so the explanation stays
readable inside Aegisub; strings and long brackets are left untouched.
"""
from __future__ import annotations

import re


class FlattenError(ValueError):
    pass


def _long_bracket(src: str, i: int) -> tuple[int, int] | None:
    """If src[i:] starts a long bracket [==[, return (level, index after the opening)."""
    m = re.match(r"\[(=*)\[", src[i:])
    if not m:
        return None
    return len(m.group(1)), i + m.end()


def flatten(src: str, keep_comments: bool = True) -> str:
    out: list[str] = []
    i, n = 0, len(src)
    line = 1
    pending_space = False

    def emit(s: str):
        nonlocal pending_space
        if pending_space and out and not out[-1].endswith(" "):
            out.append(" ")
        pending_space = False
        out.append(s)

    while i < n:
        c = src[i]
        if c in "\r\n":
            if c == "\n":
                line += 1
            pending_space = True
            i += 1
            continue
        if c in " \t":
            pending_space = True
            i += 1
            continue
        if src.startswith("--", i):
            lb = _long_bracket(src, i + 2)
            if lb:
                level, j = lb
                close = "]" + "=" * level + "]"
                end = src.find(close, j)
                if end < 0:
                    raise FlattenError(f"line {line}: unterminated block comment")
                body = src[j:end]
                line += body.count("\n")
                if keep_comments:
                    body = " ".join(body.split())
                    emit(_block_comment(body))
                    pending_space = True
                i = end + len(close)
                continue
            end = src.find("\n", i)
            end = n if end < 0 else end
            body = src[i + 2:end].strip()
            if keep_comments and body:
                emit(_block_comment(body))
                pending_space = True
            i = end
            continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    if j + 1 < n and src[j + 1] in "\r\n":
                        raise FlattenError(f"line {line}: a string continues over a line break; use \\n instead")
                    j += 2
                    continue
                if src[j] == c:
                    break
                if src[j] in "\r\n":
                    raise FlattenError(f"line {line}: unfinished string")
                j += 1
            emit(src[i:j + 1])
            i = j + 1
            continue
        if c == "[":
            lb = _long_bracket(src, i)
            if lb:
                level, j = lb
                close = "]" + "=" * level + "]"
                end = src.find(close, j)
                if end < 0:
                    raise FlattenError(f"line {line}: unterminated long string")
                body = src[j:end]
                if "\n" in body or "\r" in body:
                    raise FlattenError(f"line {line}: a [[long string]] spans several lines; it cannot be put on "
                                       "one ASS line")
                emit(src[i:end + len(close)])
                i = end + len(close)
                continue
        # ordinary token run
        j = i
        while j < n and src[j] not in " \t\r\n'\"" and not src.startswith("--", j) and \
                not (src[j] == "[" and _long_bracket(src, j)):
            j += 1
        if j == i:
            j = i + 1
        emit(src[i:j])
        i = j
    return "".join(out).strip()


def _block_comment(body: str) -> str:
    level = 0
    while ("]" + "=" * level + "]") in body:
        level += 1
    eq = "=" * level
    return f"--[{eq}[ {body} ]{eq}]"


def check_syntax(code: str, name: str = "code") -> str | None:
    """Return a Lua syntax error message, or None."""
    from lupa import luajit21
    lua = luajit21.LuaRuntime(register_eval=False, register_builtins=False)
    fn = lua.eval("function(s, n) local f, e = loadstring(s, n) if f then return nil end return e end")
    return fn(code, "=" + name)
