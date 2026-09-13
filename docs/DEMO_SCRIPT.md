# 3-Minute Demo Script (Judging)

All demo data is 100% synthetic — fake company, fake people, fake secrets.
Practice the flow once before presenting; total runtime ≈ 3 minutes.

## Setup (before the judge arrives)

```bash
pip install -r requirements.txt
python backend/app/main.py        # or: python -m uvicorn backend.app.main:app
```

Open `http://127.0.0.1:8000`. The header chip shows the honest runtime:
"CPU dev fallback" on a dev box, "Snapdragon NPU (QNN)" on a Snapdragon
Windows PC with the QNN runtime installed.

## Act 1 — The problem (30s)

> "Everyone shares screens — interviews, classes, client calls. One careless
> window can leak an API key, a student's ID, or a confidential roadmap.
> Cloud DLP can't help personal users because the *sensitive screenshot
> itself* would have to be uploaded first."

## Act 2 — Scan the developer dashboard (45s)

1. Click the **Developer Dashboard** demo card.
2. Click **Scan Locally**. Point at the privacy banner while it runs:
   *"Scanning locally — no data leaves this machine."*
3. Walk through the findings list:
   - 5 **critical**: AWS key, GitHub PAT, Google key, Slack webhook, JWT
   - 3 **high**: AWS secret + session token (entropy), "do not share" (semantic)
   - 2 **medium**: email, internal Grafana URL
4. **Privacy proof panel**: "0 outbound connections opened during scan —
   that's measured with psutil, not a promise."

## Act 3 — Semantic catches what regex can't (30s)

1. Switch to the **Confidential Slide** demo and scan.
2. > "No regex can enumerate every confidential sentence. The semantic layer
     reads the OCR text and flags meaning — 'internal roadmap', 'salary
     revision', 'do not share'."
3. Note the engine label in the UI: on this machine it says exactly which
   engine ran (`semantic-minilm` or `semantic-keyword-fallback`).

## Act 4 — Safe Share (45s)

1. Back on the dashboard scan, pick **Pixelate** (or blur/blackout).
2. Click **Create Safe Share** → drag the comparison slider.
   > "Left: what I almost shared. Right: what I can actually share."
3. Optionally uncheck one finding to show per-finding control, re-render.
4. Click **Download PNG**.

## Act 5 — Precision story (30s)

> "Detection is precise, not just noisy." Scan the **Tax Invoice**:
- The card number is flagged **only because it passes the Luhn checksum**.
- The bank account number (also 14 digits, fails Luhn) is labeled
  *Bank Account Number* from the "Account Number:" context — a different,
  correct label.
- The PAN inside the GSTIN is *not* double-flagged.
- The invoice total (Rs. 12,744.00) is correctly ignored.

## Closing (15s)

> "Everything ran on-device. The runtime panel shows the real execution
> providers — on a Snapdragon PC this becomes QNN/NPU-accelerated via ONNX
> Runtime, and we only claim that when it's genuinely loaded. The benchmark
> harness in `scripts/benchmark.py` produces the evidence files in
> `benchmarks/`."

## Q&A backup slides

- **"What about live sharing?"** — Roadmap item #2: selected-window
  scanning every N seconds; virtual camera output (#3).
- **"Why simulated OCR?"** — CPU-only dev boxes without EasyOCR/torch use
  the demo ground-truth sidecars so the pipeline is still demonstrable; the
  engine label never hides it. On a real machine `pip install easyocr`
  switches to real OCR automatically.
- **"False positives?"** — Checksum validation (Luhn/Verhoeff) plus
  context-required detectors keep precision high; the findings list lets
  the user exclude any finding before rendering the Safe Share.
