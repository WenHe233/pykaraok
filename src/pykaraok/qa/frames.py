"""Checks that need rendered frames."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .. import config
from ..ass.document import AssDocument
from ..render import ffmpeg as rf


def stream_frames(ass, t0: float, t1: float, source: rf.Source, font_dirs=None, width: int = 480):
    """Yield (time, HxWx3 uint8 array) for every frame in [t0, t1)."""
    w, h = source.size
    ow = width - width % 2
    oh = int(round(h * ow / w)) // 2 * 2
    inp, prefix = source.input_args(t0, t1 - t0)
    chain = prefix + (rf.subtitle_filter(ass, font_dirs) + "," if ass else "") + f"scale={ow}:{oh}"
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error"] + inp + \
        ["-vf", chain, "-f", "rawvideo", "-pix_fmt", "rgb24", "-fps_mode", "passthrough", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = ow * oh * 3
    i = 0
    step = 1.0 / source.fps_float
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield t0 + i * step, np.frombuffer(buf, np.uint8).reshape(oh, ow, 3)
            i += 1
    finally:
        proc.stdout.close()
        proc.wait()


def find_jumps(ass, t0: float, t1: float, source: rf.Source, font_dirs=None, width: int = 480,
               threshold: int = 40, min_pixels: int = 60, top: int = 10) -> dict:
    """Frames that differ from both neighbours while the neighbours agree: a one-frame glitch.

    Rendered on a plain black background so only subtitle changes count.
    """
    bg = rf.Source(None, "black", source.size, source.fps)
    frames = list(stream_frames(ass, t0, t1, bg, font_dirs, width))
    hits = []
    for i in range(1, len(frames) - 1):
        a = frames[i - 1][1].astype(np.int16)
        b = frames[i][1].astype(np.int16)
        c = frames[i + 1][1].astype(np.int16)
        dev = np.abs(b - (a + c) // 2).max(axis=2)
        n_dev = int((dev > threshold).sum())
        if n_dev < min_pixels:
            continue
        n_ac = int((np.abs(c - a).max(axis=2) > threshold).sum())
        if n_dev > 3 * max(n_ac, 1):
            ys, xs = np.nonzero(dev > threshold)
            scale = source.size[0] / frames[i][1].shape[1]
            hits.append({"time": round(frames[i][0], 3), "pixels": n_dev, "neighbour_pixels": n_ac,
                         "box": [int(xs.min() * scale), int(ys.min() * scale),
                                 int(xs.max() * scale), int(ys.max() * scale)]})
    hits.sort(key=lambda h: -h["pixels"])
    return {"frames": len(frames), "jumps": hits[:top], "count": len(hits)}


def steady_diff(original, effect, source: rf.Source, font_dirs=None, styles=None, outdir=None,
                threshold: int = 24, strip_k: str = "auto") -> dict:
    """Render original and effect file at the middle of each original lyric line and compare pixels.

    Used to make sure the effect leaves the static look (position, font, size) of the
    user's lines unchanged when that is the brief.  The whole frame is compared, so
    lines shown at the same time (e.g. JP and CN) are reported together.

    strip_k: "auto" removes karaoke tags from the original when it has any (otherwise
    unsung syllables render in SecondaryColour and every karaoke effect "differs");
    "yes" / "no" force it.
    """
    import re
    import tempfile

    from PIL import Image
    doc = AssDocument.load(original)
    lines = [e for e in doc.events if not e["comment"] and e["effect"] != "fx"]
    if styles:
        lines = [e for e in lines if e["style"] in styles]
    ktag = re.compile(r"\\(?:kf|ko|kt|k|K)\d+(?:\.\d+)?")
    has_k = any(ktag.search(e["text"]) for e in lines)
    do_strip = strip_k == "yes" or (strip_k == "auto" and has_k)
    tmp = Path(tempfile.mkdtemp(prefix="pykaraok-steady-"))
    ref = Path(original)
    if do_strip:
        for e in doc.events:
            if not e["comment"] and ktag.search(e["text"]):
                e["text"] = ktag.sub("", e["text"]).replace("{}", "")
                e.pop("raw", None)
        ref = tmp / "original_sung.ass"
        doc.save(ref)
    groups: dict[tuple, list[str]] = {}
    for e in lines:
        groups.setdefault((e["start_time"], e["end_time"]), [])
        if e["style"] not in groups[(e["start_time"], e["end_time"])]:
            groups[(e["start_time"], e["end_time"])].append(e["style"])
    results = []
    outdir = Path(outdir) if outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
    try:
        for (st, en), sts in sorted(groups.items()):
            t = (st + en) / 2000
            fa, fb = tmp / "a.png", tmp / "b.png"
            rf.frame(ref, t, fa, source, font_dirs)
            rf.frame(effect, t, fb, source, font_dirs)
            a = np.asarray(Image.open(fa).convert("RGB"), np.int16)
            b = np.asarray(Image.open(fb).convert("RGB"), np.int16)
            d = np.abs(a - b).max(axis=2)
            n = int((d > threshold).sum())
            item = {"time": round(t, 3), "styles": sts, "max_diff": int(d.max()), "pixels_over": n}
            if n:
                ys, xs = np.nonzero(d > threshold)
                item["box"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                if outdir:
                    vis = np.clip(d * 6, 0, 255).astype(np.uint8)
                    pth = outdir / f"diff_{int(t * 1000)}.png"
                    Image.fromarray(vis).save(pth)
                    item["diff_image"] = str(pth)
            results.append(item)
    finally:
        for f in tmp.glob("*"):
            f.unlink()
        tmp.rmdir()
    changed = [r for r in results if r["pixels_over"]]
    return {"lines": len(results), "changed": len(changed), "stripped_k": do_strip, "results": results}
