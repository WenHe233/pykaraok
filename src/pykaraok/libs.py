"""Third-party Aegisub Lua/MoonScript libraries for use inside templates.

Yutils is vendored (MIT).  The others are installed into the cache include dir
(config.libs_dir()) by `pykaraok setup libs`:

  * from DependencyControl feeds at pinned commits, every file checked against
    the SHA-1 in the feed, native libraries picked for this platform; or
  * with --from DIR, copied from an existing automation/include folder.

Once installed, `require "ILL.ILL"` etc. work in `code once` lines: .moon files
are compiled with moonc on first load and native DLLs are found by requireffi.
"""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
import urllib.request
from pathlib import Path

from . import config

# feed url (pinned), channel ref used in raw URLs, modules to install
FEEDS = {
    "ILL": ("https://raw.githubusercontent.com/TypesettingTools/ILL-Aegisub-Scripts/"
            "f3e581c04d74669bcf724f9fd2e49cf6c5c7607b/DependencyControl.json",
            "f3e581c04d74669bcf724f9fd2e49cf6c5c7607b",
            ["ILL.ILL", "clipper2.clipper2"]),
    "ffi-experiments": ("https://raw.githubusercontent.com/TypesettingTools/ffi-experiments/"
                        "3d31f77b752a95c1e4186582dcaf39a21301c5a9/DependencyControl.json",
                        None,
                        ["requireffi.requireffi"]),
}
OPTIONAL = {"img": ("ILL", ["ILL.IMG"])}   # image tracing (gif/png/jpeg decoders as DLLs)

# directories copied by --from, when present
LOCAL_DIRS = ["ILL", "clipper2", "requireffi", "ZF", "zpolyclipping", "zimg", "arch", "lyger", "petzku",
              "phos", "Oboro", "ln", "0x"]
LOCAL_FILES = ["Yutils.lua"]

KNOWN_MODULES = {
    "Yutils": "Yutils",
    "ILL": "ILL.ILL",
    "clipper2": "clipper2.clipper2",
    "requireffi": "requireffi.requireffi",
    "karaOK": "ln.kara",
    "0x.color": "0x.color",
    "ZF": "ZF.main",
    "arch.Math": "arch.Math",
}


def _platform() -> str:
    osname = {"win32": "Windows", "darwin": "OSX"}.get(sys.platform, "Linux")
    arch = "x64" if platform.machine().lower() in ("amd64", "x86_64", "arm64", "aarch64") else "x86"
    return f"{osname}-{arch}"


def _fetch(url: str, attempts: int = 4) -> bytes:
    import time
    for i in range(attempts):
        try:
            return urllib.request.urlopen(url, timeout=120).read()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(1.5 * (i + 1))


def _subst(s: str, vars: dict) -> str:
    for _ in range(5):
        changed = False
        for k, v in vars.items():
            token = "@{" + k + "}"
            if token in s and v is not None:
                s = s.replace(token, v)
                changed = True
        if not changed:
            break
    return s


def install_from_feed(feed_url: str, modules: list[str], channel_ref: str | None, dest: Path, log=print) -> list[str]:
    feed = json.loads(_fetch(feed_url))
    plat = _platform()
    done = []
    for name in modules:
        m = feed["modules"][name]
        chan_name = next(iter(m["channels"]))
        chan = m["channels"][chan_name]
        ns_path = name.replace(".", "/")
        vars = {"feedName": feed.get("name"), "channel": channel_ref or chan_name, "namespace": name,
                "namespacePath": ns_path, "scriptName": m.get("name"), "version": chan.get("version")}
        # resolve fileBaseUrl from the outside in: feed -> module -> channel
        base = feed.get("fileBaseUrl")
        if base:
            vars["fileBaseUrl"] = _subst(base, vars)
        for level in (m, chan):
            if level.get("fileBaseUrl"):
                vars["fileBaseUrl"] = _subst(level["fileBaseUrl"], vars)
        for f in chan.get("files", []):
            if f.get("platform") and f["platform"] != plat:
                continue
            if not f.get("url"):
                continue
            fvars = dict(vars, fileName=f["name"])
            url = _subst(f["url"], fvars)
            target = dest / (ns_path + f["name"])
            log(f"downloading {url}")
            data = _fetch(url)
            sha = hashlib.sha1(data).hexdigest()
            if f.get("sha1") and sha.lower() != f["sha1"].lower():
                raise RuntimeError(f"SHA-1 mismatch for {url}: got {sha}, feed says {f['sha1']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            done.append(str(target))
    return done


def install_from_dir(source: Path, dest: Path, log=print) -> list[str]:
    done = []
    for d in LOCAL_DIRS:
        src = source / d
        if src.is_dir():
            log(f"copying {src}")
            shutil.copytree(src, dest / d, dirs_exist_ok=True)
            for ext in (".moon", ".lua"):
                f = source / (d + ext)
                if f.exists():
                    shutil.copy2(f, dest / f.name)
            done.append(str(dest / d))
    for f in LOCAL_FILES:
        if (source / f).exists() and f != "Yutils.lua":
            shutil.copy2(source / f, dest / f)
            done.append(str(dest / f))
    return done


def setup(source: str | None = None, extras: list[str] | None = None, log=print) -> dict:
    from .aegi.moon import download_moonc, find_moonc
    if not find_moonc():
        download_moonc(log)
    dest = config.libs_dir()
    if source:
        return {"copied": install_from_dir(Path(source), dest, log)}
    out = {}
    for key, (url, ref, mods) in FEEDS.items():
        out[key] = install_from_feed(url, mods, ref, dest, log)
    for extra in extras or []:
        feed_key, mods = OPTIONAL[extra]
        url, ref, _ = FEEDS[feed_key]
        out[extra] = install_from_feed(url, mods, ref, dest, log)
    return out


def status() -> dict:
    dirs = [Path(p) for p in config.default_include_dirs()]
    out = {}
    for label, mod in KNOWN_MODULES.items():
        rel = mod.replace(".", "/")
        hit = None
        for d in dirs:
            for cand in (d / (rel + ".lua"), d / (rel + ".moon"), d / rel / "init.lua"):
                if cand.exists():
                    hit = str(cand)
                    break
            if hit:
                break
        out[label] = hit or "missing"
    return out
