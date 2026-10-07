"""Video information through ffprobe."""
from __future__ import annotations

import functools
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from .. import config


@functools.lru_cache(maxsize=32)
def _probe(path: str) -> dict:
    out = subprocess.run([config.ffprobe(), "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", path], capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8", "replace"))


def video_info(path: str | Path) -> dict:
    data = _probe(str(Path(path).resolve()))
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if v is None:
        raise ValueError(f"{path} has no video stream")
    rate = v.get("avg_frame_rate") or v.get("r_frame_rate") or "24000/1001"
    if rate in ("0/0", "0/1"):
        rate = v.get("r_frame_rate", "24000/1001")
    fr = Fraction(rate)
    dur = float(data.get("format", {}).get("duration") or v.get("duration") or 0)
    start = float(v.get("start_time") or data.get("format", {}).get("start_time") or 0)
    return {
        "width": int(v["width"]), "height": int(v["height"]),
        "fps": (fr.numerator, fr.denominator), "fps_float": float(fr),
        "duration": dur, "start_time": start,
        "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
        "codec": v.get("codec_name"),
    }


def frame_times(path: str | Path, start: float | None = None, end: float | None = None) -> list[float]:
    """Presentation times (seconds) of the video frames, optionally limited to [start, end]."""
    cmd = [config.ffprobe(), "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time",
           "-of", "csv=p=0"]
    if start is not None:
        span = f"{start}%+{(end - start) if end is not None else 1e9}"
        cmd += ["-read_intervals", span]
    cmd.append(str(path))
    out = subprocess.run(cmd, capture_output=True, check=True).stdout.decode()
    times = []
    for ln in out.split():
        try:
            times.append(float(ln.strip().rstrip(",")))
        except ValueError:
            pass
    return sorted(times)
