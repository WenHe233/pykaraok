"""The0x539's KaraTemplater as a second engine.

The0x539/Aegisub-Scripts has no licence, so nothing of it is stored in this
repository: `pykaraok setup 0x539` downloads the files at a pinned commit into
the cache, and the MoonScript source is compiled with moonc when it is loaded.
karaOK (ln.kara, also unlicensed) and 0x.color are fetched the same way because
0x539 templates commonly use them.

Differences from running it inside Aegisub:
  * `main` reseeds math.random with os.time() on every run, so templates that use
    math.random differ between runs in Aegisub too.  With RunOptions.seed set,
    pykaraok seeds once and makes later math.randomseed calls no-ops.
  * frame_from_ms / ms_from_frame (used by fbf utilities) need --video or --fps.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from .. import config

MACRO_NAME = "0x539's Templater"

SOURCES = {
    # name: (repo, commit, path in repo, destination relative to cache dir)
    "templater": ("The0x539/Aegisub-Scripts", "15518cbb7c9de8f66cd038f422904785c0880a81",
                  "src/0x.KaraTemplater.moon", "0x539/0x.KaraTemplater.moon"),
    "0x.color": ("The0x539/Aegisub-Scripts", "15518cbb7c9de8f66cd038f422904785c0880a81",
                 "src/color.lua", "libs/0x/color.lua"),
    "ln.kara": ("lost-logarithm/karaOK", "f749c4fa64e73a7c4fd38fe2c194c875b4e6c962",
                "include/ln/kara.lua", "libs/ln/kara.lua"),
}


def templater_path() -> Path:
    p = config.cache_dir() / SOURCES["templater"][3]
    if not p.exists():
        raise FileNotFoundError("0x539 KaraTemplater is not installed; run `pykaraok setup 0x539`")
    return p


def status() -> dict:
    out = {}
    for name, (_, commit, _, dest) in SOURCES.items():
        p = config.cache_dir() / dest
        out[name] = f"{commit[:8]} {p}" if p.exists() else "missing"
    from .moon import find_moonc
    out["moonc"] = find_moonc() or "missing"
    return out


def setup(ref: str | None = None, log=print) -> dict:
    from .moon import compile_file, download_moonc, find_moonc
    if not find_moonc():
        download_moonc(log)
    done = {}
    for name, (repo, commit, path, dest) in SOURCES.items():
        use = ref if (ref and repo.startswith("The0x539")) else commit
        url = f"https://raw.githubusercontent.com/{repo}/{use}/{path}"
        log(f"downloading {url}")
        data = urllib.request.urlopen(url, timeout=60).read()
        target = config.cache_dir() / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        done[name] = str(target)
    (config.cache_dir() / "0x539" / "SOURCES.json").write_text(json.dumps(
        {k: {"repo": v[0], "commit": ref or v[1] if v[0].startswith("The0x539") else v[1], "path": v[2]}
         for k, v in SOURCES.items()}, indent=2), encoding="utf-8")
    compile_file(templater_path())          # fail early if the source does not compile
    return done
