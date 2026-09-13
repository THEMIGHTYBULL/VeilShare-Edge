"""OCR layer with three runtimes, chosen honestly at scan time.

- ``easyocr``      — real on-device OCR when the optional package is installed.
- ``simulated``    — ground-truth sidecar JSON shipped with the demo images so
                     the full pipeline is demonstrable on CPU-only dev boxes
                     with zero heavy dependencies. Clearly labeled as simulated.
- none             — no engine available; the scan reports this instead of
                     pretending to see text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "demo" / "sample_inputs"

_reader = None  # lazy EasyOCR singleton


@dataclass
class OCRItem:
    text: str
    bbox: tuple  # (x, y, w, h) in image pixels
    confidence: float


def easyocr_available() -> bool:
    try:
        import easyocr  # noqa: F401
        return True
    except Exception:
        return False


def _run_easyocr(image) -> List[OCRItem]:
    global _reader
    import numpy as np
    import easyocr

    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    arr = np.asarray(image.convert("RGB"))
    results = _reader.readtext(arr)
    items = []
    for pts, text, conf in results:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x, y = int(min(xs)), int(min(ys))
        w, h = int(max(xs) - x), int(max(ys) - y)
        items.append(OCRItem(text=text, bbox=(x, y, w, h), confidence=float(conf)))
    return items


def _sidecar_path(demo_id: str) -> Path:
    return DEMO_DIR / f"{demo_id}.json"


def load_sidecar(demo_id: str) -> List[OCRItem]:
    """Load ground-truth text boxes recorded when the demo image was drawn."""
    path = _sidecar_path(demo_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        OCRItem(text=t["text"], bbox=tuple(t["bbox"]), confidence=1.0)
        for t in data.get("texts", [])
    ]


def run_ocr(image, demo_id: Optional[str] = None, prefer: str = "auto") -> Tuple[List[OCRItem], str, str]:
    """Run OCR and return (items, engine_name, note).

    ``prefer``: "auto" | "easyocr" | "simulated".
    The returned note is surfaced to the UI so the engine in use is never
    misrepresented.
    """
    prefer = (prefer or "auto").lower()

    if prefer == "simulated":
        if demo_id:
            items = load_sidecar(demo_id)
            if items:
                return items, "simulated-sidecar", (
                    "Simulated OCR using the demo ground-truth sidecar — install "
                    "'easyocr' for real on-device OCR."
                )
        return [], "none", "Simulated OCR requested but no demo sidecar found."

    if prefer == "easyocr" or (prefer == "auto" and easyocr_available()):
        if easyocr_available():
            try:
                return _run_easyocr(image), "easyocr", "Real on-device OCR (EasyOCR)."
            except Exception as exc:  # fall back below, transparently
                note = f"EasyOCR failed ({exc}); "
        else:
            note = "EasyOCR not installed; "

    # auto path without easyocr: try demo sidecar
    if demo_id:
        items = load_sidecar(demo_id)
        if items:
            return items, "simulated-sidecar", (
                "Simulated OCR using the demo ground-truth sidecar (EasyOCR not installed)."
            )

    note = note if prefer != "auto" else ""  # type: ignore[possibly-undefined]
    return [], "none", (note or "No OCR engine available — ") + (
        "install 'easyocr' or scan a built-in demo image."
    )
