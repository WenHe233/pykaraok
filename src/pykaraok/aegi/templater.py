"""Apply karaoke templates headlessly.

Engines:
  stock   Aegisub's own automation/autoload/kara-templater.lua (vendored, 2.1.7)
  0x539   The0x539's KaraTemplater (downloaded and compiled by `pykaraok setup 0x539`)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from ..ass.document import AssDocument
from .runtime import AegiRuntime, RunOptions, ScriptError

STOCK_MACRO = "Apply karaoke template"


@dataclass
class ApplyResult:
    status: str                       # ok | cancelled | error | no_templates
    message: str = ""
    engine: str = "stock"
    can_template: bool | None = None  # what Aegisub's menu validation says (50-line rule)
    logs: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict:
        return {
            "status": self.status, "message": self.message, "engine": self.engine,
            "can_template": self.can_template, "seconds": round(self.seconds, 3),
            "warnings": self.warnings, "stats": self.stats,
            "logs": [{"level": lv, "message": m} for lv, m in self.logs],
        }


def _engine_script(engine: str) -> tuple[Path, str]:
    if engine == "stock":
        return config.STOCK_TEMPLATER, STOCK_MACRO
    if engine == "0x539":
        from . import x0539
        return x0539.templater_path(), x0539.MACRO_NAME
    raise ValueError(f"unknown engine {engine!r} (stock | 0x539)")


def event_stats(doc: AssDocument) -> dict:
    ev = doc.events
    fx = [e for e in ev if e["effect"] == "fx"]
    stats = {
        "events": len(ev),
        "fx_lines": len(fx),
        "template_lines": sum(1 for e in ev if e["comment"] and e["effect"].split(" ")[0].lower() in ("template", "code", "mixin")),
        "karaoke_lines": sum(1 for e in ev if e["effect"].lower() in ("karaoke", "kara")),
    }
    if fx:
        stats["fx_text_bytes"] = sum(len(e["text"].encode("utf-8")) for e in fx)
        stats["fx_layers"] = sorted({int(e["layer"]) for e in fx})
        stats["fx_time_range_ms"] = [min(e["start_time"] for e in fx), max(e["end_time"] for e in fx)]
    return stats


def apply_templates(doc: AssDocument, engine: str = "stock", options: RunOptions | None = None,
                    require_menu_check: bool = False) -> ApplyResult:
    """Run the templater on `doc` in place. The document is changed only when the run succeeds."""
    t0 = time.perf_counter()
    script, macro = _engine_script(engine)
    rt = AegiRuntime(doc, options, script_path=doc.path)
    res = ApplyResult(status="error", engine=engine)
    try:
        rt.load_script(script)
    except ScriptError as exc:
        res.message = str(exc)
        res.logs, res.seconds = rt.logs, time.perf_counter() - t0
        return res
    can, why = rt.validate_macro(macro)
    res.can_template = can
    if not can and require_menu_check:
        res.status = "no_templates"
        res.message = why or ("Aegisub would disable the menu item: no template line among the first 50 "
                              "dialogue lines")
        res.logs, res.seconds = rt.logs, time.perf_counter() - t0
        return res
    status, msg, _ = rt.run_macro(macro)
    res.status, res.message = status, msg
    if status == "ok":
        rt.commit_to(doc)
        res.stats = event_stats(doc)
    res.logs = rt.logs
    res.warnings = list(getattr(rt.metrics, "warnings", []))
    if engine == "stock" and can is False:
        res.warnings.append("no template line among the first 50 dialogue lines: Aegisub's "
                            "'Apply karaoke template' menu item would be disabled for this file")
    res.seconds = time.perf_counter() - t0
    return res


def apply_file(src: str | Path, dst: str | Path, engine: str = "stock",
               options: RunOptions | None = None) -> ApplyResult:
    doc = AssDocument.load(src)
    res = apply_templates(doc, engine, options)
    if res.ok:
        doc.save(dst)
        res.stats["output"] = str(dst)
        res.stats["output_bytes"] = Path(dst).stat().st_size
    return res
