"""Locations of vendored scripts, caches, Aegisub installs and extra Lua include dirs.

Every location can be overridden with an environment variable so that other
machines and other agent harnesses can use the tool without code changes:

    PYKARAOK_CACHE      cache root (compiled MoonScript, downloads, 0x539 sources)
    PYKARAOK_AEGISUB    an Aegisub ``automation`` directory (only used by ``doctor``
                        and ``setup libs --from``)
    PYKARAOK_INCLUDE    extra Lua include dirs, separated by os.pathsep
    PYKARAOK_MOONC      path to a moonc executable
    PYKARAOK_FFMPEG     path to ffmpeg (default: found on PATH)
    PYKARAOK_FFPROBE    path to ffprobe (default: found on PATH)
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = PACKAGE_DIR / "vendor"
AEGISUB_VENDOR = VENDOR_DIR / "aegisub"
LUA_DIR = PACKAGE_DIR / "aegi" / "lua"
FXLIB_DIR = PACKAGE_DIR / "fxlib"

STOCK_TEMPLATER = AEGISUB_VENDOR / "autoload" / "kara-templater.lua"
AEGISUB_INCLUDE = AEGISUB_VENDOR / "include"


def cache_dir() -> Path:
    env = os.environ.get("PYKARAOK_CACHE")
    if env:
        root = Path(env)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "pykaraok"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "pykaraok"
    root.mkdir(parents=True, exist_ok=True)
    return root


def libs_dir() -> Path:
    """Where `pykaraok setup` puts third-party Lua/Moon libraries (an include dir)."""
    d = cache_dir() / "libs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def known_aegisub_automation_dirs() -> list[Path]:
    cands = []
    env = os.environ.get("PYKARAOK_AEGISUB")
    if env:
        cands.append(Path(env))
    home = Path.home()
    cands += [
        home / "Downloads" / "aegisub-portable-64" / "aegisub-portable" / "automation",
        Path(r"C:\Program Files\Aegisub\automation"),
        Path(r"C:\Program Files (x86)\Aegisub\automation"),
        Path(os.environ.get("APPDATA", home)) / "Aegisub" / "automation",
        Path("/usr/share/aegisub/automation"),
        home / ".aegisub" / "automation",
    ]
    return [c for c in cands if (c / "include").is_dir() or (c / "autoload").is_dir()]


def env_include_dirs() -> list[Path]:
    env = os.environ.get("PYKARAOK_INCLUDE", "")
    return [Path(p) for p in env.split(os.pathsep) if p.strip()]


def default_include_dirs(extra: list[str | Path] | None = None) -> list[Path]:
    """Include path handed to the Lua runtime, in search order.

    1. pykaraok's own fxlib (so templates can ``include("pykaraok.lua")``)
    2. vendored Aegisub include dir (karaskel, utils, compiled aegisub.* modules)
    3. libraries installed by ``pykaraok setup`` (Yutils, ILL, karaOK, 0x.color ...)
    4. user supplied dirs (``--include`` and PYKARAOK_INCLUDE)
    """
    dirs = [FXLIB_DIR, AEGISUB_INCLUDE, VENDOR_DIR / "yutils", libs_dir()]
    dirs += [Path(p) for p in (extra or [])]
    dirs += env_include_dirs()
    seen, out = set(), []
    for d in dirs:
        key = str(Path(d).resolve()).lower()
        if key not in seen and Path(d).is_dir():
            seen.add(key)
            out.append(Path(d))
    return out


def find_tool(name: str, env_var: str) -> str | None:
    env = os.environ.get(env_var)
    if env and Path(env).exists():
        return env
    found = shutil.which(name)
    if found:
        return found
    local = cache_dir() / "tools" / (name + (".exe" if sys.platform == "win32" else ""))
    if local.exists():
        return str(local)
    return None


def ffmpeg() -> str:
    exe = find_tool("ffmpeg", "PYKARAOK_FFMPEG")
    if not exe:
        raise RuntimeError("ffmpeg not found; install it or set PYKARAOK_FFMPEG")
    return exe


def ffprobe() -> str:
    exe = find_tool("ffprobe", "PYKARAOK_FFPROBE")
    if not exe:
        raise RuntimeError("ffprobe not found; install it or set PYKARAOK_FFPROBE")
    return exe
