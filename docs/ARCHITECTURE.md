# Architecture

VeilShare Edge is a local-first privacy firewall: every stage of the pipeline
runs on the user's machine. No screenshot pixels, OCR text, or findings ever
leave the process.

## High-level flow

```text
┌──────────────────────────────────────────────────────────────────┐
│ User machine (Snapdragon-powered HP PC, or any dev box)          │
│                                                                  │
│  Source ──► Scan pipeline ──► Findings ──► Safe Share            │
│  (demo / upload / mss capture)      │             │              │
│                                     ▼             ▼              │
│                            Risk summary    Redaction renderer    │
│                                     │             │              │
│                            Privacy proof    PNG (in memory)      │
└──────────────────────────────────────────────────────────────────┘
```

## Repository layout

| Path | Purpose |
|---|---|
| `backend/app/` | FastAPI service + all detection logic |
| `frontend/` | Local web UI (vanilla JS, no build step, served by the backend) |
| `demo/sample_inputs/` | Synthetic demo screenshots + OCR ground-truth sidecars |
| `scripts/` | Demo generator + benchmark harness |
| `tests/` | Pytest suite (58 tests: checksums, detectors, redaction, API) |
| `docs/` | Architecture, API, demo script, privacy, deployment, submission docs |
| `models/` | Model strategy + fetch instructions (weights are never committed) |
| `benchmarks/` | Recorded performance evidence (honest numbers only) |
| `assets/screenshots/` | UI screenshots for the submission (placeholders until demo day) |

## Backend modules

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI app, endpoints, in-memory scan store, static UI mount |
| `pipeline.py` | Orchestrates OCR → detectors → semantics → risk, wrapped in a network monitor |
| `ocr.py` | OCR engine selection: EasyOCR (real) / sidecar (simulated) / none — always labeled |
| `detectors.py` | Regex + checksum (Luhn, Verhoeff) + entropy detectors with overlap resolution |
| `semantic.py` | MiniLM semantic classifier when available; keyword fallback otherwise (labeled) |
| `risk.py` | Severity scoring and summary |
| `redact.py` | Blur / blackout / pixelate rendering (Pillow, in-process) |
| `privacy.py` | psutil connection snapshot diff = measurable privacy proof |
| `runtime_info.py` | ONNX Runtime providers, QNN presence, CPU/platform facts |
| `demo_data.py` | Draws the synthetic demo screenshots and records ground-truth boxes |
| `capture.py` | Optional live screen capture via `mss` |
| `checksums.py` | Luhn + Verhoeff implementations (single source of truth) |

## Scan request lifecycle

1. `POST /api/scan` receives an upload, a demo id, or a capture request.
2. `pipeline.run_scan()`:
   - `NetworkMonitor.start()` snapshots this process's connections.
   - OCR runs (engine chosen by availability; name recorded verbatim).
   - Every OCR line goes through the detector registry. Matches are sorted
     by severity, then specificity; overlapping character spans are claimed
     by the strongest detector only (a JWT is not also reported as a
     "high-entropy string").
   - The semantic engine adds confidential-content findings (with its engine
     name attached).
   - `NetworkMonitor.stop()` diffs the snapshot → measured privacy proof.
3. Findings, summary, timings, privacy, and runtime info are returned.
4. The PIL image is held in an in-memory `ScanStore` (capacity 32, never
   written to disk) so `POST /api/redact` can render the Safe Share.

## Detection design notes

- **Structured secrets** (AWS/GitHub/Slack/Google/OpenAI keys, JWTs, private
  key headers, credentialed URLs) are matched with anchored patterns.
- **Checksum-validated identifiers**: card numbers must pass Luhn;
  Aadhaar-like numbers must pass Verhoeff. This kills most false positives
  from random digit runs.
- **Context detectors**: `password:`/`token:` assignments and
  `Account Number: …` labels require nearby context words, not just shape.
- **Entropy fallback**: long, mixed-class, high-entropy strings are flagged
  as secret-like even when no vendor pattern matches.
- **Semantic layer** catches meaning-based leaks ("internal roadmap",
  "salary sheet") that regexes cannot enumerate.

## Honesty model (important for judging)

Every response reports exactly which components ran:

- `ocr_engine`: `easyocr` | `simulated-sidecar` | `none`
- `semantic_engine`: `semantic-minilm` | `semantic-keyword-fallback`
- `runtime.acceleration_status`: `qnn-ready` | `cpu-fallback` | `onnxruntime-missing`

The UI displays these verbatim. NPU acceleration is only ever claimed when
`QNNExecutionProvider` is actually present in ONNX Runtime.
