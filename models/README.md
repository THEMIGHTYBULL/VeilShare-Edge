# Model Strategy

VeilShare Edge uses two AI models at inference time. **Model weights are
never committed to this repository** (size + licensing); they are fetched
locally per the instructions below. `models/assets/` is git-ignored.

## 1. OCR model — EasyOCR

- **Role:** detect and recognize text in screenshots / screen regions.
  Screen leaks are visual — regex cannot see an API key until OCR turns
  pixels into text.
- **Input:** RGB screenshot frame (numpy array).
- **Output:** text regions, recognized strings, confidence scores.
- **Deployment:** EasyOCR runs directly on-device (CPU threads on dev
  machines; the Qualcomm AI Hub optimized asset + QNN path on Snapdragon
  targets).

```bash
pip install easyocr
```

That's the whole setup — `backend/app/ocr.py` auto-selects EasyOCR whenever
it is importable and labels the engine `easyocr` in every scan response.

## 2. Semantic sensitivity model — MiniLM

- **Role:** classify OCR text snippets as confidential by *meaning*
  ("internal roadmap", "salary sheet", "do not share") — beyond what fixed
  patterns can enumerate.
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (or a fine-tuned
  DistilBERT classifier, if time allows).
- **Fallback:** a deterministic keyword engine (`backend/app/semantic.py`)
  keeps the feature working on minimal installs; the response always reports
  which engine ran (`semantic-minilm` vs `semantic-keyword-fallback`).

```bash
pip install sentence-transformers
```

## Target: Qualcomm AI Hub optimized assets

On the Snapdragon target the intended path is:

```text
PyTorch / ONNX model
 → Qualcomm AI Hub Workbench compile & profile
 → optimized ONNX / QNN asset in models/assets/
 → ONNX Runtime + QNNExecutionProvider (Hexagon NPU / HTP)
```

```bash
pip install qai-hub-models
qai-hub-models info easyocr          # confirm current packaging commands
# fetch/compile assets into models/assets/ (git-ignored)
```

Because AI Hub packaging evolves, always confirm exact commands with
`qai-hub-models info <model>` rather than trusting stale docs. Record any
profiling session links in `benchmarks/qualcomm_ai_hub_profile_links.md`.

## Directory conventions

```text
models/
├── README.md          # this file
└── assets/            # fetched/compiled weights — NEVER committed
    └── .gitkeep
```
