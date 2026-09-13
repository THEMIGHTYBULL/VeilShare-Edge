# Snapdragon Deployment (Windows on Snapdragon / HP PCs)

VeilShare Edge develops anywhere Python runs, but the target is a
Snapdragon-powered HP PC (Windows 11 ARM64) with ONNX Runtime's QNN
Execution Provider driving the Hexagon NPU.

## Development mode (any machine)

```bash
pip install -r requirements.txt
python backend/app/main.py
```

The runtime panel will honestly show `CPU dev fallback`. That is expected on
non-Snapdragon hardware.

## Target mode (Snapdragon Windows PC)

### 1. Base environment

Install Python 3.10+ (ARM64) and confirm the platform:

```powershell
python -c "import platform; print(platform.machine())"   # expect ARM64
```

### 2. ONNX Runtime with QNN

Install the QNN-enabled ONNX Runtime build for Windows ARM64:

```powershell
pip install onnxruntime-qnn
```

Verify the provider is genuinely present — this is the moment the app is
allowed to claim NPU acceleration:

```powershell
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# must include QNNExecutionProvider
```

Start VeilShare Edge and check the header chip / runtime panel — it should
switch to **"Snapdragon NPU (QNN)"** automatically. No code changes needed:
`backend/app/runtime_info.py` detects the provider at runtime.

### 3. Real OCR (EasyOCR)

```powershell
pip install easyocr
```

The OCR layer auto-selects EasyOCR when it is importable
(`backend/app/ocr.py`); scans switch from `simulated-sidecar` to `easyocr`
with no configuration.

### 4. Optional: live capture

```powershell
pip install mss
```

Enables `POST /api/capture` and the UI's capture flow.

## Qualcomm AI Hub path (model optimization)

The intended optimization path for the OCR and embedding models:

```text
PyTorch / ONNX source model
 → Qualcomm AI Hub Workbench compile & profile
 → optimized ONNX / QNN-compatible asset
 → ONNX Runtime + QNNExecutionProvider (Hexagon NPU / HTP)
```

Check current packaging commands with `qai-hub-models info <model>` — model
packaging evolves, so confirm against the live docs rather than copying
stale commands. Store fetched assets under `models/assets/` (git-ignored)
and record profiling links in `benchmarks/qualcomm_ai_hub_profile_links.md`.

See `models/README.md` for the model strategy details.

## Honesty checklist before claiming NPU numbers

- [ ] `QNNExecutionProvider` appears in `ort.get_available_providers()` **on the target PC**
- [ ] Runtime panel in the UI shows `qnn-ready`
- [ ] Benchmark run recorded with `python scripts/benchmark.py …` on the device
- [ ] Report saved to `benchmarks/snapdragon_qnn_run.json`
- [ ] No fabricated numbers anywhere in the repo (placeholder files stay
      marked "not yet run" until a real run replaces them)

**NPU acceleration must never be claimed from a CPU dev machine.** The
recorded dev run in `benchmarks/linux_cpu_dev_run.json` is clearly labeled
`cpu-fallback` — that is the standard of honesty this repo keeps.
