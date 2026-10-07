"""agi::vfr::Framerate (libaegisub/common/vfr.cpp) for frame_from_ms / ms_from_frame.

Aegisub uses the frame timestamps of the loaded video.  Pass either a
constant rate (``Framerate.cfr(24000, 1001)``) or the list of frame times in
milliseconds (``Framerate.from_timecodes``; see render.ffmpeg.frame_times).
"""
from __future__ import annotations

EXACT, START, END = 0, 1, 2
_DEFAULT_DEN = 1000000000


def _cdiv(a: int, b: int) -> int:
    """C integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


class Framerate:
    def __init__(self, numerator: int, denominator: int, timecodes: list[int], last: int = 0):
        self.numerator = numerator
        self.denominator = denominator
        self.timecodes = timecodes
        self.last = last

    @classmethod
    def cfr(cls, num: int, den: int = 1) -> "Framerate":
        if num <= 0 or den <= 0:
            raise ValueError("numerator and denominator must be positive")
        return cls(int(num), int(den), [0], 0)

    @classmethod
    def from_fps(cls, fps: float) -> "Framerate":
        return cls(int(fps * _DEFAULT_DEN), _DEFAULT_DEN, [0], 0)

    @classmethod
    def from_timecodes(cls, timecodes: list[int]) -> "Framerate":
        tc = [int(t) for t in timecodes]
        if len(tc) <= 1:
            raise ValueError("need at least two timecodes")
        base = tc[0]
        tc = [t - base for t in tc]           # normalize_timecodes
        den = _DEFAULT_DEN
        num = (len(tc) - 1) * den * 1000 // tc[-1]
        last = (len(tc) - 1) * den * 1000
        return cls(num, den, tc, last)

    def frame_at_time(self, ms: int, kind: int = START) -> int:
        ms = int(ms)
        if kind == START:
            return self.frame_at_time(ms - 1, EXACT) + 1
        if kind == END:
            return self.frame_at_time(ms - 1, EXACT)
        num, den, tc = self.numerator, self.denominator, self.timecodes
        if ms < 0:
            return _cdiv(_cdiv(ms * num, den) - 999, 1000)
        if ms > tc[-1]:
            return _cdiv((ms + 1) * num - self.last - _cdiv(num, 2) + (1000 * den - 1), 1000 * den) + len(tc) - 2
        # number of timecodes <= ms, minus one
        lo, hi = 0, len(tc)
        while lo < hi:
            mid = (lo + hi) // 2
            if tc[mid] <= ms:
                lo = mid + 1
            else:
                hi = mid
        return lo - 1

    def time_at_frame(self, frame: int, kind: int = START) -> int:
        frame = int(frame)
        if kind == START:
            prev = self.time_at_frame(frame - 1, EXACT)
            cur = self.time_at_frame(frame, EXACT)
            return prev + _cdiv(cur - prev + 1, 2)
        if kind == END:
            cur = self.time_at_frame(frame, EXACT)
            nxt = self.time_at_frame(frame + 1, EXACT)
            return cur + _cdiv(nxt - cur + 1, 2)
        num, den, tc = self.numerator, self.denominator, self.timecodes
        if num == 0:
            return 0
        if frame < 0:
            return _cdiv(frame * den * 1000, num)
        if frame >= len(tc):
            past = frame - len(tc) + 1
            return _cdiv(past * 1000 * den + self.last + _cdiv(num, 2), num)
        return tc[frame]
