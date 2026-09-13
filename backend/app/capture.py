"""Live screen capture (optional `mss` dependency).

On a desktop machine (`pip install mss`) this grabs the primary monitor or a
region. On headless dev boxes it fails gracefully so the rest of the app
still works with uploads and demo images.
"""

from __future__ import annotations

from typing import Optional


def capture_screen(monitor_index: int = 0, region: Optional[tuple] = None):
    """Return a PIL Image of a monitor or region, or raise RuntimeError."""
    try:
        import mss
    except ImportError as exc:
        raise RuntimeError(
            "Screen capture requires the optional 'mss' package: pip install mss"
        ) from exc

    import io

    from PIL import Image

    with mss.mss() as sct:
        target = {"mon": monitor_index + 1, **({"left": region[0], "top": region[1],
                                                "width": region[2], "height": region[3]}
                                               if region else {})}
        shot = sct.grab(sct.monitors[monitor_index + 1] if not region else target)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return img
