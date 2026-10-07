"""Render subtitles with libass through ffmpeg.

Known pitfalls handled here (each cost time in earlier projects):
  * filter arguments: Windows drive colons and backslashes must be escaped
  * timestamps: `-ss` before `-i` plus `-copyts` keeps the original video time,
    so the ass filter renders the right moment
  * fontsdir takes a single directory (see fonts.single_dir)
  * yuv420p needs even crop/scale sizes
  * `-vsync` is gone in new ffmpeg builds; use -fps_mode
  * without a video, a lavfi colour source is shifted with setpts instead of
    seeking (seeking a generated source renders every frame up to t)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .. import config, fonts as fontmod
from . import probe


def esc(path: str | Path) -> str:
    """Quote a path for use as a filter option value."""
    s = str(Path(path).resolve()).replace("\\", "/")
    s = s.replace("'", r"'\''").replace(":", r"\:")
    return f"'{s}'"


def _label_font() -> str:
    if sys.platform == "win32":
        f = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
        if f.exists():
            return "fontfile=" + esc(f)
    return "font=Sans"


def _even(v: float) -> int:
    v = int(round(v))
    return v - (v % 2)


@dataclass
class Source:
    """What the subtitles are drawn on: a video file or a plain background."""
    video: Path | None = None
    background: str = "gray"            # used when video is None: any ffmpeg colour, or "checker"
    size: tuple[int, int] = (1920, 1080)
    fps: tuple[int, int] = (24000, 1001)

    @classmethod
    def make(cls, video=None, background="gray", size=None, fps=None, doc=None):
        if video:
            info = probe.video_info(video)
            return cls(Path(video), background, (info["width"], info["height"]), info["fps"])
        if size is None and doc is not None:
            size = doc.resolution()
        return cls(None, background, tuple(size or (1920, 1080)), tuple(fps or (24000, 1001)))

    @property
    def fps_float(self) -> float:
        return self.fps[0] / self.fps[1]

    def input_args(self, t0: float, duration: float) -> tuple[list[str], str]:
        """ffmpeg input arguments and a filter prefix that makes frame pts equal video time."""
        if self.video:
            return ["-ss", f"{max(0.0, t0):.3f}", "-copyts", "-t", f"{duration:.3f}", "-i", str(self.video)], ""
        w, h = self.size
        rate = f"{self.fps[0]}/{self.fps[1]}"
        if self.background == "checker":
            src = (f"color=c=0x707070:s={w}x{h}:r={rate}:d={duration:.3f},"
                   f"geq=lum='if(mod(floor(X/32)+floor(Y/32),2),150,100)':cb=128:cr=128")
        else:
            src = f"color=c={self.background}:s={w}x{h}:r={rate}:d={duration:.3f}"
        return ["-f", "lavfi", "-i", src], f"setpts=PTS+{t0:.3f}/TB,"


def subtitle_filter(ass_path, font_dirs=None) -> str:
    f = f"ass=filename={esc(ass_path)}"
    fd = fontmod.single_dir(font_dirs or [])
    if fd:
        f += f":fontsdir={esc(fd)}"
    return f


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd) + "\n" + proc.stderr.decode("utf-8", "replace")[-3000:])


def _ff() -> list[str]:
    return [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]


def _crop_scale(crop, width, size):
    """Filter chain for an optional crop (one rect, or several rects stacked vertically) and a resize."""
    parts = []
    w, h = size
    if crop:
        rects = [crop] if isinstance(crop[0], (int, float)) else list(crop)
        rects = [(int(x), int(y), _even(cw), _even(ch)) for x, y, cw, ch in rects]
        if len(rects) == 1:
            x, y, cw, ch = rects[0]
            parts.append(f"crop={cw}:{ch}:{x}:{y}")
            w, h = cw, ch
        else:
            # vstack needs equal widths: narrower bands are padded on the right
            n = len(rects)
            maxw = max(r[2] for r in rects)
            labels = "".join(f"[c{i}]" for i in range(n))
            g = f"split={n}{labels}"
            for i, (x, y, cw, ch) in enumerate(rects):
                pad = f",pad={maxw}:{ch}:0:0:color=0x303030" if cw < maxw else ""
                g += f";[c{i}]crop={cw}:{ch}:{x}:{y}{pad}[d{i}]"
            g += ";" + "".join(f"[d{i}]" for i in range(n)) + f"vstack=inputs={n}"
            parts.append(g)
            w = maxw
            h = sum(r[3] for r in rects)
    if width and width != w:
        sh = _even(h * width / w)
        parts.append(f"scale={_even(width)}:{sh}:flags=lanczos")
        w, h = width, sh
    return parts, (w, h)


def frame(ass, t: float, out, source: Source, font_dirs=None, crop=None, width=None, label=False) -> Path:
    """Render one frame at time t (seconds)."""
    inp, prefix = source.input_args(t, 1.0 / source.fps_float * 2)
    chain = [prefix + subtitle_filter(ass, font_dirs)] if ass else ([prefix.rstrip(",")] if prefix else [])
    cs, (ow, _oh) = _crop_scale(crop, width, source.size)
    chain += cs
    if label:
        fs = max(11, min(20, int(ow / 40)))
        chain.append(f"drawtext={_label_font()}:text='%{{pts\\:hms}}':x=3:y=h-th-3:fontsize={fs}"
                     ":fontcolor=yellow:box=1:boxcolor=black@0.5")
    run(_ff() + inp + ["-vf", ",".join(c for c in chain if c), "-frames:v", "1", str(out)])
    return Path(out)


def sheet(ass, t0: float, t1: float, out, source: Source, font_dirs=None, step: float | None = None,
          fps: float | None = None, cols: int = 6, crop=None, width: int = 480, label=True) -> dict:
    """Frames from t0 to t1 tiled into one image (single ffmpeg pass)."""
    if step is None:
        step = 1.0 / fps if fps else max((t1 - t0) / 24, 1.0 / source.fps_float)
    n = max(1, int((t1 - t0) / step + 1e-6) + 1)
    rows = (n + cols - 1) // cols
    inp, prefix = source.input_args(t0, t1 - t0 + step)
    times = [t0 + i * step for i in range(n)]
    half = 0.5 / source.fps_float
    sel = "+".join(f"between(t,{t - half:.4f},{t + half - 1e-4:.4f})" for t in times)
    chain = [prefix + f"select='{sel}'"]
    if ass:
        chain.append(subtitle_filter(ass, font_dirs))
    cs, _ = _crop_scale(crop, width, source.size)
    chain += cs
    if label:
        chain.append(f"drawtext={_label_font()}:text='%{{pts\\:hms}}':x=4:y=4:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.5")
    chain.append(f"tile={cols}x{rows}:padding=2:color=0x303030")
    run(_ff() + inp + ["-vf", ",".join(chain), "-fps_mode", "passthrough", "-frames:v", "1", str(out)])
    return {"output": str(out), "times": [round(t, 3) for t in times], "cols": cols, "rows": rows}


def sample_sheet(ass, times: list[float], out, source: Source, font_dirs=None, cols: int = 5, crop=None,
                 width: int = 384, label=True, captions: list[str] | None = None, jobs: int = 4) -> dict:
    """Frames at arbitrary times tiled into one image (row-major, in the given order).

    Close times are rendered in one decoding pass; widely spaced ones are
    rendered in parallel with fast seeking and tiled with Pillow.
    """
    from concurrent.futures import ThreadPoolExecutor

    from PIL import Image, ImageDraw

    times = list(times)
    rows = (len(times) + cols - 1) // cols
    tmpdir = Path(tempfile.mkdtemp(prefix="pykaraok-"))
    try:
        def one(i_t):
            i, t = i_t
            f = tmpdir / f"{i:04d}.png"
            frame(ass, t, f, source, font_dirs, crop=crop, width=width, label=label)
            return f
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            files = list(ex.map(one, enumerate(times)))
        tiles = [Image.open(f).convert("RGB") for f in files]
        tw, th = tiles[0].size
        cap_h = 18 if captions else 0
        pad = 2
        sheet_img = Image.new("RGB", (cols * (tw + pad) - pad, rows * (th + cap_h + pad) - pad), (48, 48, 48))
        draw = ImageDraw.Draw(sheet_img)
        for i, im in enumerate(tiles):
            r, c = divmod(i, cols)
            x, y = c * (tw + pad), r * (th + cap_h + pad)
            sheet_img.paste(im, (x, y + cap_h))
            if captions and i < len(captions):
                draw.text((x + 4, y + 2), captions[i], fill=(255, 230, 120))
        sheet_img.save(out)
    finally:
        for f in tmpdir.glob("*"):
            f.unlink()
        tmpdir.rmdir()
    return {"output": str(out), "times": [round(t, 3) for t in times], "cols": cols, "rows": rows}


def preview(ass, out, t0: float, t1: float, source: Source, font_dirs=None, bitrate: str = "4500k",
            width: int | None = None, audio: bool = True, crf: int | None = None) -> dict:
    """Burn the subtitles into an H.264 mp4 of the range [t0, t1] (timestamps start at 0)."""
    dur = t1 - t0
    if source.video:
        inp = ["-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(source.video)]
        prefix = f"setpts=PTS+{t0:.3f}/TB,"
    else:
        inp, prefix = source.input_args(t0, dur)
    chain = [prefix + subtitle_filter(ass, font_dirs), "setpts=PTS-STARTPTS"]
    cs, _ = _crop_scale(None, width, source.size)
    chain += cs
    chain.append("format=yuv420p")
    cmd = _ff() + inp + ["-vf", ",".join(chain), "-c:v", "libx264", "-preset", "medium"]
    if crf is not None:
        cmd += ["-crf", str(crf)]
    else:
        cmd += ["-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    has_audio = bool(source.video) and audio and probe.video_info(source.video)["has_audio"]
    if has_audio:
        cmd += ["-af", "asetpts=PTS-STARTPTS", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(out)]
    run(cmd)
    return {"output": str(out), "bytes": Path(out).stat().st_size, "seconds": round(dur, 3)}


def render_time(ass, t0: float, t1: float, source: Source, font_dirs=None, width: int | None = None) -> dict:
    """Wall-clock cost of rendering the range with libass (decode cost measured separately)."""
    import time
    inp, prefix = source.input_args(t0, t1 - t0)
    base = _ff() + inp
    tail = ["-f", "null", "-"]
    t = time.perf_counter()
    run(base + (["-vf", prefix.rstrip(",")] if prefix else []) + tail)
    plain = time.perf_counter() - t
    t = time.perf_counter()
    run(base + ["-vf", prefix + subtitle_filter(ass, font_dirs)] + tail)
    with_subs = time.perf_counter() - t
    frames = max(1, int((t1 - t0) * source.fps_float))
    per = (with_subs - plain) / frames * 1000
    return {"frames": frames, "seconds_without_subs": round(plain, 2), "seconds_with_subs": round(with_subs, 2),
            "ms_per_frame": round(per, 2), "budget_ms_per_frame": round(1000 / source.fps_float, 2)}
