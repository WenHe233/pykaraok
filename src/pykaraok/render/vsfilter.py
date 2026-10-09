"""Optional: render a frame with VSFilter through its CSRI interface (Windows, 64-bit DLL).

The user's deliverables only target libass; this exists to spot effects that
fall apart under VSFilter / xy-VSFilter, so a warning can be given.  The DLL is
taken from an Aegisub install (csri/VSFilter.dll) or PYKARAOK_VSFILTER.
Fonts must be installed or loaded into this process (metrics.gdi.load_font_dir).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
from pathlib import Path

from .. import config
from . import ffmpeg as rf

CSRI_F_BGR_ = 0x102


class _Frame(ctypes.Structure):
    _fields_ = [("pixfmt", ctypes.c_int), ("planes", ctypes.c_void_p * 4), ("strides", ctypes.c_ssize_t * 4)]


class _Fmt(ctypes.Structure):
    _fields_ = [("pixfmt", ctypes.c_int), ("width", ctypes.c_uint), ("height", ctypes.c_uint)]


def find_dll() -> Path | None:
    env = os.environ.get("PYKARAOK_VSFILTER")
    if env and Path(env).exists():
        return Path(env)
    for auto in config.known_aegisub_automation_dirs():
        cand = auto.parent / "csri" / "VSFilter.dll"
        if cand.exists():
            return cand
    return None


def frame(ass, t: float, out, source: rf.Source, font_dirs=()) -> Path:
    """Render the frame ffmpeg.frame renders for time t, with VSFilter instead of libass.

    That is the first frame at or after t (Source.first_frame), with the subtitles at
    its timestamp, so the two images show the same moment.  Without a video the
    background is plain gray.
    """
    dll_path = find_dll()
    if not dll_path:
        raise RuntimeError("VSFilter.dll not found; set PYKARAOK_VSFILTER")
    if font_dirs:
        from ..metrics.gdi import load_font_dir
        for d in font_dirs:
            load_font_dir(d)
    w, h = source.size
    ft = source.frame_time(source.first_frame(t))
    dll = ctypes.CDLL(str(dll_path))
    dll.csri_renderer_default.restype = ctypes.c_void_p
    dll.csri_open_file.restype = ctypes.c_void_p
    dll.csri_open_file.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    dll.csri_request_fmt.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Fmt)]
    dll.csri_render.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Frame), ctypes.c_double]
    dll.csri_close.argtypes = [ctypes.c_void_p]
    inst = dll.csri_open_file(dll.csri_renderer_default(), str(Path(ass).resolve()).encode("utf-8"), None)
    if not inst:
        raise RuntimeError("csri_open_file failed")
    try:
        fmt = _Fmt(CSRI_F_BGR_, w, h)
        if dll.csri_request_fmt(inst, ctypes.byref(fmt)) != 0:
            raise RuntimeError("csri_request_fmt failed")
        if source.video:
            inp, _ = source.input_args(t, 2 / source.fps_float)     # the seek ffmpeg.frame uses
            raw = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error"] + inp +
                                 ["-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr0", "-"],
                                 capture_output=True, check=True).stdout
            if len(raw) != w * h * 4:
                raise RuntimeError(f"no video frame at {ft:.3f}s")
        else:
            raw = bytes([0x60, 0x60, 0x60, 0]) * (w * h)
        buf = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        fr = _Frame()
        fr.pixfmt = CSRI_F_BGR_
        fr.planes[0] = ctypes.addressof(buf)
        fr.strides[0] = w * 4
        # VSFilter truncates the time to whole ms, and a frame time on a whole ms can fall a hair
        # below it in floating point (frame 24 at 23.976 fps, 1.001 s, rendered at 1000 ms): add 50 ns
        dll.csri_render(inst, ctypes.byref(fr), ctypes.c_double(ft + 5e-8))
        from PIL import Image
        Image.frombuffer("RGBX", (w, h), bytes(buf), "raw", "BGRX", 0, 1).convert("RGB").save(out)
    finally:
        dll.csri_close(inst)
    return Path(out)
