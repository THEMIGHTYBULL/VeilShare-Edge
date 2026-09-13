"""Demo data generator tests."""

import json
from pathlib import Path

from backend.app import demo_data
from backend.app.checksums import verhoeff_valid

DEMO_DIR = Path(demo_data.DEMO_DIR)


def test_generate_all_creates_every_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_data, "DEMO_DIR", tmp_path)
    written = demo_data.generate_all(force=True)
    assert len(written) == 2 * len(demo_data.DEMO_SPECS)
    for spec in demo_data.DEMO_SPECS:
        assert (tmp_path / f"{spec['id']}.png").exists()
        assert (tmp_path / f"{spec['id']}.json").exists()


def test_sidecars_in_bounds_and_synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_data, "DEMO_DIR", tmp_path)
    demo_data.generate_all(force=True)
    from PIL import Image

    for spec in demo_data.DEMO_SPECS:
        sidecar = json.loads((tmp_path / f"{spec['id']}.json").read_text())
        img = Image.open(tmp_path / f"{spec['id']}.png")
        W, H = img.size
        assert sidecar["texts"], f"{spec['id']} has no tracked text"
        for t in sidecar["texts"]:
            x, y, w, h = t["bbox"]
            assert 0 <= x and 0 <= y and x + w <= W and y + h <= H, t


def test_demo_inputs_available():
    # PNGs are committed; JSON sidecars are generated on first boot
    # (they contain synthetic tokens that trip GitHub push protection).
    demo_data.generate_all()
    for spec in demo_data.DEMO_SPECS:
        assert DEMO_DIR.joinpath(f"{spec['id']}.png").exists(), spec["id"]
        assert DEMO_DIR.joinpath(f"{spec['id']}.json").exists(), spec["id"]


def test_student_portal_aadhaar_is_verhoeff_valid():
    import re

    sidecar = json.loads((DEMO_DIR / "fake_student_portal.json").read_text())
    # the Aadhaar value is the unique "NNNN NNNN NNNN" formatted text item
    # (the phone "+91 98765 43210" also has 12 digits, so match the shape)
    aadhaar_line = next(
        t["text"] for t in sidecar["texts"]
        if re.fullmatch(r"\d{4} \d{4} \d{4}", t["text"].strip())
    )
    digits = aadhaar_line.replace(" ", "")
    assert len(digits) == 12
    assert verhoeff_valid(digits)
