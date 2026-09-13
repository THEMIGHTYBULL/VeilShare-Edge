"""Shared pytest configuration: make the repo root importable and ensure the
synthetic demo inputs exist (their sidecars are generated, not committed)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import demo_data  # noqa: E402

demo_data.generate_all()
