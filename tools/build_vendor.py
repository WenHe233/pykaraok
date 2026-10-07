"""Compile the vendored Aegisub .moon modules into committed .lua files.

Run after updating anything under src/pykaraok/vendor/aegisub/moon-src:

    python tools/build_vendor.py

The compiled files go to vendor/aegisub/include/aegisub/... so that the stock
templater runs without moonc being installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pykaraok.aegi import moon  # noqa: E402

SRC = ROOT / "src" / "pykaraok" / "vendor" / "aegisub" / "moon-src"
DST = ROOT / "src" / "pykaraok" / "vendor" / "aegisub" / "include"

HEADER = "-- Compiled from {src} by moonc {ver} (tools/build_vendor.py). Do not edit.\n"


def main() -> int:
    if not moon.find_moonc():
        moon.download_moonc()
    n = 0
    for src in sorted(SRC.rglob("*.moon")):
        rel = src.relative_to(SRC).with_suffix(".lua")
        lua = moon.compile_text(src.read_text(encoding="utf-8-sig"), str(src))
        out = DST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(HEADER.format(src=src.relative_to(SRC).as_posix(), ver=moon.MOONC_VERSION) + lua,
                       encoding="utf-8", newline="\n")
        print(f"compiled {rel.as_posix()}")
        n += 1
    print(f"{n} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
