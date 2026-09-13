"""Redaction renderer tests."""

import pytest
from PIL import Image

from backend.app.redact import MODES, expand_box, redact_boxes, redact_findings


def make_image():
    # deterministic image with a high-contrast block where redaction happens
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    px = img.load()
    for y in range(40, 60):
        for x in range(40, 60):
            px[x, y] = (255, 255, 255)
    return img


@pytest.mark.parametrize("mode", MODES)
def test_outside_box_untouched(mode):
    img = make_image()
    out = redact_boxes(img, [(40, 40, 20, 20)], mode=mode)
    assert out.getpixel((5, 5)) == img.getpixel((5, 5))
    assert out.getpixel((95, 95)) == img.getpixel((95, 95))
    # inside the box the pixels must change
    assert out.getpixel((50, 50)) != img.getpixel((50, 50))


def test_blackout_is_black():
    out = redact_boxes(make_image(), [(40, 40, 20, 20)], mode="blackout")
    assert out.getpixel((50, 50)) == (10, 10, 12)


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        redact_boxes(make_image(), [(0, 0, 10, 10)], mode="frobnicate")


def test_box_expansion_clamped():
    # pad is a fraction of the box size, clamped to the image bounds
    x0, y0, x1, y1 = expand_box((5, 5, 10, 10), (100, 100), pad_frac=1.0)
    assert (x0, y0, x1, y1) == (0, 0, 25, 25)
    # a box near the bottom-right cannot grow past the image
    x0, y0, x1, y1 = expand_box((90, 90, 20, 20), (100, 100), pad_frac=1.0)
    assert (x0, y0, x1, y1) == (70, 70, 100, 100)


def test_redact_findings_filters_ids():
    img = make_image()
    findings = [
        {"id": "F01", "bbox": [40, 40, 20, 20]},
        {"id": "F02", "bbox": [10, 10, 20, 20]},
    ]
    out = redact_findings(img, findings, mode="blackout", finding_ids=["F02"])
    assert out.getpixel((20, 20)) == (10, 10, 12)   # redacted
    assert out.getpixel((50, 50)) != (10, 10, 12)   # untouched
