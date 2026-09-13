#!/usr/bin/env python3
"""VeilShare Edge benchmark harness — honest numbers only.

Measures OCR latency, detection latency, total scan latency, peak memory,
execution provider, and privacy behavior over repeated runs of the full local
pipeline. Writes a JSON report suitable for the benchmarks/ folder.

Usage:
    python scripts/benchmark.py --input demo/sample_inputs/fake_dashboard.png --repeat 20
    python scripts/benchmark.py --demo fake_dashboard --repeat 20 --output benchmarks/my_run.json
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from backend.app import demo_data, pipeline  # noqa: E402

demo_data.generate_all()  # sidecars are generated, not committed


def pct(values, p):
    """Simple percentile without numpy dependency in the report path."""
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1))))
    return ordered[k]


def summarize(values):
    return {
        "mean_ms": round(statistics.mean(values), 2),
        "median_ms": round(statistics.median(values), 2),
        "p95_ms": round(pct(values, 95), 2),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="path to a screenshot (demo sidecars are auto-detected)")
    src.add_argument("--demo", help="built-in demo id, e.g. fake_dashboard")
    parser.add_argument("--repeat", type=int, default=20)
    parser.add_argument("--ocr", default="auto", choices=["auto", "easyocr", "simulated"])
    parser.add_argument("--output", help="write JSON report to this path")
    args = parser.parse_args()

    if args.demo:
        demo_id = args.demo
        path = demo_data.demo_path(demo_id)
        if not path.exists():
            demo_data.generate_all()
    else:
        path = Path(args.input).resolve()
        if not path.exists():
            print(f"error: input not found: {path}", file=sys.stderr)
            return 2
        demo_id = None
        sidecar = path.with_suffix(".json")
        if sidecar.exists() and path.parent == (ROOT / "demo" / "sample_inputs").resolve():
            demo_id = path.stem  # sidecar available → simulated OCR can be used

    image = Image.open(path).convert("RGB")

    # Warm-up run (imports, font caches, provider init)
    warm = pipeline.run_scan(image, demo_id=demo_id, prefer_ocr=args.ocr)

    import psutil

    proc = psutil.Process()
    rss_start = proc.memory_info().rss
    runs = []
    peak_rss = rss_start
    for _ in range(args.repeat):
        result = pipeline.run_scan(image, demo_id=demo_id, prefer_ocr=args.ocr)
        runs.append(result["timings"])
        peak_rss = max(peak_rss, proc.memory_info().rss)

    report = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "repeat": args.repeat,
            "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "processor": platform.processor() or platform.machine(),
            "python": platform.python_version(),
            "ocr_engine": result["ocr_engine"],
            "semantic_engine": result["semantic_engine"],
            "onnxruntime": result["runtime"].get("onnxruntime"),
            "acceleration_status": result["runtime"].get("acceleration_status"),
        },
        "latency": {
            "ocr": summarize([r["ocr_ms"] for r in runs]),
            "detect": summarize([r["detect_ms"] for r in runs]),
            "total": summarize([r["total_ms"] for r in runs]),
        },
        "memory": {
            "rss_start_mb": round(rss_start / (1024 * 1024), 1),
            "rss_peak_mb": round(peak_rss / (1024 * 1024), 1),
        },
        "findings_per_run": result["summary"]["total_findings"],
        "privacy_last_run": result["privacy"],
        "runs": runs,
    }

    output = json.dumps(report, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
        print(f"report written to {out_path}")

    print(f"\nVeilShare Edge benchmark — {report['meta']['input']} x {args.repeat}")
    print(f"  OCR engine        : {report['meta']['ocr_engine']}")
    print(f"  Semantic engine   : {report['meta']['semantic_engine']}")
    print(f"  Acceleration      : {report['meta']['acceleration_status']}")
    print(f"  OCR latency       : {report['latency']['ocr']['mean_ms']:.1f} ms mean "
          f"(p95 {report['latency']['ocr']['p95_ms']:.1f} ms)")
    print(f"  Detection latency : {report['latency']['detect']['mean_ms']:.1f} ms mean "
          f"(p95 {report['latency']['detect']['p95_ms']:.1f} ms)")
    print(f"  Total scan latency: {report['latency']['total']['mean_ms']:.1f} ms mean "
          f"(p95 {report['latency']['total']['p95_ms']:.1f} ms)")
    print(f"  Peak RSS          : {report['memory']['rss_peak_mb']:.1f} MB")
    print(f"  New outbound connections during scans: "
          f"{report['privacy_last_run'].get('new_outbound_connections_during_scan')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
