"""Font directories: zip font packs, merging several dirs into one for libass.

A font directory always means the font files directly in it (see font_files).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path

from . import config

FONT_EXTS = (".ttf", ".otf", ".ttc", ".otc")


def _cache_key(paths: list[Path]) -> str:
    h = hashlib.sha1()
    for p in paths:
        st = p.stat()
        h.update(f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8"))
    return h.hexdigest()[:16]


def unpack_zip(zpath: Path) -> Path:
    """Extract the font files of a zip font pack into the cache; returns the directory."""
    zpath = Path(zpath)
    out = config.cache_dir() / "fonts" / ("zip-" + _cache_key([zpath]))
    if out.is_dir() and any(out.iterdir()):
        return out
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        for i, info in enumerate(zf.infolist()):
            name = info.filename
            if name.lower().endswith(FONT_EXTS):
                # zip member names of CJK packs are often mis-decoded; keep them unique and ASCII
                (out / f"{i:04d}{Path(name).suffix.lower()}").write_bytes(zf.read(info))
    return out


def resolve(font_args) -> list[Path]:
    """Turn --fonts arguments (dirs, font files, zip packs) into directories/files usable everywhere."""
    out: list[Path] = []
    for a in font_args or []:
        p = Path(a)
        if not p.exists():
            raise FileNotFoundError(f"font path not found: {a}")
        if p.is_file() and p.suffix.lower() == ".zip":
            out.append(unpack_zip(p))
        else:
            out.append(p)
    return out


def font_files(paths, exts=FONT_EXTS) -> list[Path]:
    """Font files of --fonts entries: a file as given, a directory's top level only.

    Subfolders are not searched: libass reads only the files directly in its
    fontsdir, and measuring must see the same fonts as rendering.  Project
    folders often keep whole font collections in subfolders.
    """
    files = []
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
        elif p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in exts and f.is_file())
    return files


def single_dir(paths) -> Path | None:
    """libass takes one fontsdir and reads every file directly in it, videos included.

    A lone directory holding nothing but font files is used as is; otherwise the
    font_files are linked (or copied) into a cached directory.
    """
    paths = [Path(p) for p in paths or []]
    if not paths:
        return None
    if len(paths) == 1 and paths[0].is_dir() and \
            all(f.suffix.lower() in FONT_EXTS and f.is_file() for f in paths[0].iterdir()):
        return paths[0]
    files = font_files(paths)
    out = config.cache_dir() / "fonts" / ("merged-" + _cache_key(files))
    if out.is_dir():
        return out
    # fill a temporary dir first so that an interrupted run leaves no partial dir behind
    tmp = out.with_name(f"{out.name}.tmp{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for i, f in enumerate(files):
        dst = tmp / f"{i:04d}{f.suffix.lower()}"
        try:
            os.link(f, dst)
        except OSError:
            shutil.copy2(f, dst)
    try:
        tmp.rename(out)
    except OSError:  # made by another process meanwhile, or a file in tmp is still open
        if not out.is_dir():
            return tmp
        shutil.rmtree(tmp, ignore_errors=True)
    return out
