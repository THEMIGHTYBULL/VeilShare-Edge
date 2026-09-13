# Submission Checklist — Snapdragon AI Lab Build & Present Challenge

Map from challenge expectations → evidence in this repository.

## Solution overview

**VeilShare Edge** — on-device privacy firewall for screen sharing and
screenshots: scan a screen/window/upload locally, detect exposed secrets and
PII with on-device OCR + deterministic detectors + a semantic layer, then
render a redacted "Safe Share" image. Runtime principle: sensitive screen
content is processed locally; nothing is uploaded.

## Evidence map

| Challenge expectation | Where to find it |
|---|---|
| Working MVP | `backend/app/` + `frontend/` — run `python backend/app/main.py` and open `http://127.0.0.1:8000` |
| Problem & solution narrative | `README.md` §1–2, `docs/DEMO_SCRIPT.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| AI model strategy (OCR + semantic) | `README.md` §5, `models/README.md` |
| Snapdragon / QNN integration path | `README.md` §6, `docs/SNAPDRAGON_DEPLOYMENT.md` |
| On-device processing claims | `docs/PRIVACY.md`, `backend/app/privacy.py` (measured per scan) |
| Benchmark evidence | `scripts/benchmark.py`, `benchmarks/` (recorded runs + placeholders clearly marked) |
| Demo plan with synthetic data | `docs/DEMO_SCRIPT.md`, `backend/app/demo_data.py` |
| Tests | `tests/` — 58 tests, `python -m pytest tests/ -q` |
| License | `LICENSE` (MIT) |

## Pre-submission checklist

- [ ] All tests green: `python -m pytest tests/ -q`
- [ ] App boots: `python backend/app/main.py` → open `http://127.0.0.1:8000`
- [ ] All four demo scans work from the UI
- [ ] Safe Share render works in all three modes (blur/blackout/pixelate)
- [ ] Privacy proof shows 0 outbound connections on each scan
- [ ] Runtime panel shows the truth for this machine (cpu-fallback is fine)
- [ ] Record a benchmark run: `python scripts/benchmark.py --input demo/sample_inputs/fake_dashboard.png --repeat 20 --output benchmarks/<your-run>.json`
- [ ] (If on Snapdragon hardware) `pip install onnxruntime-qnn`, verify
      `QNNExecutionProvider`, record `benchmarks/snapdragon_qnn_run.json`
- [ ] Capture UI screenshots into `assets/screenshots/` (dashboard, risk
      overlay, safe share, runtime panel)
- [ ] Screen-record the 3-minute demo using `docs/DEMO_SCRIPT.md`
- [ ] No real secrets or personal data anywhere in the repo
- [ ] No fabricated performance numbers — placeholders stay "not yet run"

## Key honesty commitments (say these out loud when presenting)

1. NPU acceleration is claimed **only** when QNNExecutionProvider is loaded.
2. Every scan reports which OCR and semantic engine actually ran.
3. Privacy proof is measured (psutil connection diff), not asserted.
4. Benchmark files that have not been run yet say so explicitly.
