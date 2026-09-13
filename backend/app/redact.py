"""Local redaction renderer (Safe Share).

Modes: blur | blackout | pixelate. All rendering happens in-process with
Pillow — no image data ever leaves the machine.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from PIL import Image, ImageDraw, ImageFilter

MODES = ("blur", "blackout", "pixelate")


def expand_box(bbox: Sequence[int], image_size, pad_frac: float = 0.12):
    """Grow a box by ``pad_frac`` on each side (clamped to the image)."""
    x, y, w, h = [int(v) for v in bbox[:4]]
    W, H = image_size
    dx, dy = int(w * pad_frac), int(h * pad_frac)
    x0, y0 = max(0, x - dx), max(0, y - dy)
    x1, y1 = min(W, x + w + dx), min(H, y + h + dy)
    return x0, y0, x1, y1


def redact_boxes(image: Image.Image, boxes: Iterable[Sequence[int]], mode: str = "blur") -> Image.Image:
    """Return a copy of ``image`` with every box redacted using ``mode``."""
    if mode not in MODES:
        raise ValueError(f"unknown redaction mode '{mode}' (expected one of {MODES})")

    out = image.convert("RGB").copy()
    W, H = out.size
    for bbox in boxes:
        if not bbox or len(bbox) < 4:
            continue
        x0, y0, x1, y1 = expand_box(bbox, (W, H))
        if x1 <= x0 or y1 <= y0:
            continue
        region = out.crop((x0, y0, x1, y1))
        if mode == "blackout":
            draw = ImageDraw.Draw(out)
            draw.rectangle((x0, y0, x1, y1), fill=(10, 10, 12))
        elif mode == "pixelate":
            w, h = x1 - x0, y1 - y0
            small = region.resize((max(1, w // 10), max(1, h // 10)), Image.BOX)
            out.paste(small.resize((w, h), Image.NEAREST), (x0, y0))
        elif mode == "blur":
            radius = max(8, min(x1 - x0, y1 - y0) // 6)
            out.paste(region.filter(ImageFilter.GaussianBlur(radius=radius)), (x0, y0))
    return out


def redact_findings(image: Image.Image, findings: List[dict], mode: str = "blur",
                    finding_ids=None) -> Image.Image:
    """Redact the bboxes of the given findings (all of them if ids is None)."""
    selected = findings if finding_ids is None else [f for f in findings if f["id"] in set(finding_ids)]
    boxes = [f["bbox"] for f in selected if f.get("bbox")]
    return redact_boxes(image, boxes, mode=mode)
