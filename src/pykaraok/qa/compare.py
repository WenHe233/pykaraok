"""Compare the events of two subtitle files and classify every difference.

Used by regression tests and by `pykaraok diff`.  Categories:

  identical      the formatted lines are equal
  time_round     only start/end differ, by at most 10 ms (centisecond rounding)
  extradata      only the {=N} extradata references differ
  numeric        same text skeleton, numbers differ (positions, clip coordinates ...);
                 reports the largest absolute difference
  structural     anything else
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ass import codec
from ..ass.document import AssDocument, format_event

_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_HEX = re.compile(r"&H([0-9A-Fa-f]+)&?")


def _skeleton(text: str) -> str:
    return _NUM.sub("#", _HEX.sub("&H?&", text))


def _color_delta(ta: str, tb: str) -> int:
    ca, cb = _HEX.findall(ta), _HEX.findall(tb)
    best = 0
    for x, y in zip(ca, cb):
        vx, vy = int(x, 16), int(y, 16)
        for shift in (0, 8, 16, 24):
            best = max(best, abs(((vx >> shift) & 0xFF) - ((vy >> shift) & 0xFF)))
    return best


@dataclass
class DiffReport:
    total_a: int
    total_b: int
    counts: dict = field(default_factory=dict)
    max_numeric_delta: float = 0.0
    max_color_delta: int = 0
    max_time_delta_ms: int = 0
    examples: list = field(default_factory=list)

    @property
    def only_benign(self) -> bool:
        return self.total_a == self.total_b and not self.counts.get("structural")

    def to_dict(self) -> dict:
        return {"lines_a": self.total_a, "lines_b": self.total_b, "counts": self.counts,
                "max_numeric_delta": round(self.max_numeric_delta, 4),
                "max_color_delta": self.max_color_delta,
                "max_time_delta_ms": self.max_time_delta_ms, "examples": self.examples}


def _rounded(e: dict) -> tuple[int, int]:
    return (codec.round_cs(codec.clamp_time(e["start_time"])), codec.round_cs(codec.clamp_time(e["end_time"])))


def compare_events(a: list[dict], b: list[dict], max_examples: int = 5) -> DiffReport:
    rep = DiffReport(len(a), len(b))
    counts: dict[str, int] = {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    for x, y in zip(a, b):
        fx, fy = format_event(x), format_event(y)
        if fx == fy:
            bump("identical")
            continue
        same_fields = all(x[k] == y[k] for k in ("comment", "layer", "style", "actor", "margin_l",
                                                  "margin_r", "margin_t", "effect", "text"))
        (sa, ea), (sb, eb) = _rounded(x), _rounded(y)
        dt = max(abs(sa - sb), abs(ea - eb))
        if same_fields and dt == 0 and x.get("extra_ids") != y.get("extra_ids"):
            bump("extradata")
            continue
        if same_fields:
            rep.max_time_delta_ms = max(rep.max_time_delta_ms, dt)
            bump("time_round" if dt <= 10 else "structural")
            if dt > 10 and len(rep.examples) < max_examples:
                rep.examples.append({"a": fx, "b": fy})
            continue
        ta, tb = x["text"], y["text"]
        if _skeleton(ta) == _skeleton(tb) and all(x[k] == y[k] for k in ("comment", "layer", "style", "effect")):
            na = [float(v) for v in _NUM.findall(_HEX.sub("", ta))]
            nb = [float(v) for v in _NUM.findall(_HEX.sub("", tb))]
            rep.max_color_delta = max(rep.max_color_delta, _color_delta(ta, tb))
            delta = max((abs(p - q) for p, q in zip(na, nb)), default=0.0)
            rep.max_numeric_delta = max(rep.max_numeric_delta, delta)
            rep.max_time_delta_ms = max(rep.max_time_delta_ms, dt)
            bump("numeric")
            continue
        bump("structural")
        if len(rep.examples) < max_examples:
            rep.examples.append({"a": fx, "b": fy})
    if len(a) != len(b):
        counts["count_mismatch"] = abs(len(a) - len(b))
    rep.counts = counts
    return rep


def compare_docs(a: AssDocument, b: AssDocument, effect: str | None = "fx", max_examples: int = 5) -> DiffReport:
    ea = [e for e in a.events if effect is None or e["effect"] == effect]
    eb = [e for e in b.events if effect is None or e["effect"] == effect]
    return compare_events(ea, eb, max_examples)
