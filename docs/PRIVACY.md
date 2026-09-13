# Privacy Model

VeilShare Edge exists to *prevent* leaks, so its own privacy posture must be
verifiable, not asserted.

## Data flow guarantees

| Data | Where it goes |
|---|---|
| Screenshot pixels | RAM only — in-memory `ScanStore` (max 32 scans), never written to disk |
| OCR text | RAM only, same lifecycle as the scan |
| Findings / redacted PNG | Returned to the same local client that requested them |
| Audit/history | Not implemented in the MVP by design (roadmap: metadata-only SQLite) |

- The scan pipeline (`backend/app/pipeline.py`) performs **zero network I/O**.
  Audit it: OCR, detectors, semantics fallback, redaction, and risk scoring
  are all pure local computation.
- Cloud usage is limited to *development-time* model fetching/optimization
  via Qualcomm AI Hub — an explicit developer action, never part of a scan.

## Measurable proof, not promises

Every scan response includes a `privacy` block produced by
`backend/app/privacy.py`:

```json
{
  "monitor": "psutil (process-level)",
  "new_outbound_connections_during_scan": 0,
  "cloud_calls_during_scan": 0
}
```

`NetworkMonitor` snapshots this process's TCP/UDP connections immediately
before and after the scan and reports any new **established outbound**
connection. The UI shows this number for every single scan. On systems where
psutil lacks privileges the monitor reports `unavailable` honestly instead
of showing a fake zero.

The benchmark harness records the same measurement across all runs
(`benchmarks/*.json` → `privacy_last_run`).

## Server binding

`backend/app/main.py` binds to `127.0.0.1` by default: the app is not
reachable from the network. `VEILSHARE_HOST`/`VEILSHARE_PORT` exist for
containerized development, not for exposing the app.

## Demo data policy

Every demo image is 100% synthetic (see `backend/app/demo_data.py`):
documented AWS example keys, Luhn-valid test card numbers, a Verhoeff-valid
random 12-digit number, fake people at fake domains. **Never add real
secrets or real personal identifiers to this repository.**

## Honest labeling

The app never overstates its AI or hardware:

- `ocr_engine` — `easyocr` | `simulated-sidecar` | `none`
- `semantic_engine` — `semantic-minilm` | `semantic-keyword-fallback`
- `runtime.acceleration_status` — `qnn-ready` | `cpu-fallback` | `onnxruntime-missing`

All three are displayed verbatim in the UI.

## Limitations (known and disclosed)

- The process-level connection monitor sees this process's sockets; it is
  evidence about the scan pipeline, not a system-wide guarantee.
- A determined leak (e.g. the user reading a secret aloud) is out of scope
  for a visual redaction tool (roadmap: local ASR).
- OCR can miss text that is very small, low-contrast, or partially occluded;
  redaction quality is bounded by OCR recall.
- This tool reduces accidental disclosure risk; it is not a replacement for
  enterprise DLP policy.
