"""MoonScript -> Lua compilation through the official ``moonc`` binary.

Aegisub compiles .moon files at load time with moonscript.lua, which needs the
lpeg C module that lupa's LuaJIT does not have.  We call ``moonc -p`` instead
and cache the output by content hash, so every .moon file is compiled once.
"""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .. import config

MOONC_VERSION = "v0.7.0"
_RELEASE = "https://github.com/leafo/moonscript/releases/download/{v}/moonscript-{v}-{plat}.{ext}"


class MoonCompileError(RuntimeError):
    pass


def find_moonc() -> str | None:
    return config.find_tool("moonc", "PYKARAOK_MOONC")


def download_moonc(log=print) -> str:
    """Download the official moonc release binary into the pykaraok cache."""
    if sys.platform == "win32":
        plat, ext = "windows-x86_64", "zip"
    elif sys.platform.startswith("linux"):
        plat, ext = "linux-x86_64", "tar.gz"
    else:
        raise MoonCompileError("no prebuilt moonc for this platform; install moonscript and set PYKARAOK_MOONC")
    url = _RELEASE.format(v=MOONC_VERSION, plat=plat, ext=ext)
    dest = config.cache_dir() / "tools"
    dest.mkdir(parents=True, exist_ok=True)
    log(f"downloading {url}")
    data = urllib.request.urlopen(url, timeout=60).read()
    if ext == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if Path(name).name in ("moonc.exe", "moon.exe"):
                    (dest / Path(name).name).write_bytes(z.read(name))
    else:
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            for m in t.getmembers():
                if Path(m.name).name in ("moonc", "moon"):
                    target = dest / Path(m.name).name
                    target.write_bytes(t.extractfile(m).read())
                    target.chmod(0o755)
    exe = find_moonc()
    if not exe:
        raise MoonCompileError("moonc download finished but the binary was not found")
    return exe


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith("﻿") else text


def compile_text(source: str, name: str = "<moon>", moonc: str | None = None) -> str:
    """Compile MoonScript source text to Lua source text."""
    moonc = moonc or find_moonc()
    if not moonc:
        raise MoonCompileError(
            f"cannot compile {name}: moonc not found. Run `pykaraok setup moonc` or set PYKARAOK_MOONC")
    source = _strip_bom(source)
    fd, tmp = tempfile.mkstemp(suffix=".moon")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(source)
        proc = subprocess.run([moonc, "-p", tmp], capture_output=True)
    finally:
        os.unlink(tmp)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").replace(tmp, name)
        raise MoonCompileError(f"moonc failed on {name}:\n{err}")
    return proc.stdout.decode("utf-8")


def compile_cached(source: str, name: str = "<moon>") -> str:
    key = hashlib.sha1((MOONC_VERSION + "\0" + _strip_bom(source)).encode("utf-8")).hexdigest()
    cdir = config.cache_dir() / "moon"
    cdir.mkdir(parents=True, exist_ok=True)
    cached = cdir / (key + ".lua")
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    lua = compile_text(source, name)
    tmp = cached.with_suffix(".tmp")
    tmp.write_text(lua, encoding="utf-8", newline="\n")
    tmp.replace(cached)
    return lua


def compile_file(path: str | Path) -> str:
    path = Path(path)
    return compile_cached(path.read_text(encoding="utf-8-sig"), str(path))
