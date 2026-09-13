#!/usr/bin/env python3
"""Regenerate the synthetic demo screenshots and their OCR sidecars.

Usage:
    python scripts/generate_demo_inputs.py [--force]

All data is synthetic: fake company, fake people, fake secrets. The sidecar
JSON next to each PNG records the ground-truth text boxes so the OCR layer
can simulate OCR on machines without EasyOCR installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import demo_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="regenerate even if files exist")
    args = parser.parse_args()

    written = demo_data.generate_all(force=args.force)
    if not written:
        print("Demo inputs already present (use --force to regenerate).")
        return 0

    for path in written:
        print(f"wrote {path.relative_to(ROOT)}")
    print("\nAll demo content is synthetic. Never add real secrets to these images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
