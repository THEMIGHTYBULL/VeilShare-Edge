"""The local scan pipeline shared by the API, benchmark harness, and tests.

capture/upload → OCR → deterministic detectors + semantic engine →
risk summary → redaction-ready result, wrapped in a network monitor so every
scan ships its own privacy proof and timings.
"""

from __future__ import annotations

import time
from typing import Optional

from . import detectors, risk, runtime_info, semantic
from .ocr import run_ocr
from .privacy import NetworkMonitor
from .risk import sort_findings


def run_scan(image, demo_id: Optional[str] = None, prefer_ocr: str = "auto") -> dict:
    """Scan a PIL image end-to-end. All processing is local."""
    mon = NetworkMonitor()
    mon.start()

    t0 = time.perf_counter()
    ocr_items, ocr_engine, ocr_note = run_ocr(image, demo_id=demo_id, prefer=prefer_ocr)
    t1 = time.perf_counter()

    findings = detectors.scan_ocr_items(ocr_items)
    semantic_findings, semantic_engine = semantic.analyze(ocr_items)
    findings.extend(semantic_findings)

    mon.stop()
    t2 = time.perf_counter()

    findings = sort_findings(findings)
    # re-number after sorting so F01 is the top-left most severe item
    for i, f in enumerate(findings, 1):
        f["id"] = f"F{i:02d}"

    summary = risk.summarize(findings)
    return {
        "image_size": list(image.size),
        "ocr_engine": ocr_engine,
        "ocr_note": ocr_note,
        "ocr_items": len(ocr_items),
        "semantic_engine": semantic_engine,
        "findings": findings,
        "summary": summary,
        "timings": {
            "ocr_ms": round((t1 - t0) * 1000, 2),
            "detect_ms": round((t2 - t1) * 1000, 2),
            "total_ms": round((t2 - t0) * 1000, 2),
        },
        "privacy": mon.result(),
        "runtime": runtime_info.runtime_panel(),
    }
