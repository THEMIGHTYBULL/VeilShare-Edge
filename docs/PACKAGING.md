# Packaging — Windows executable (.exe)

VeilShare Edge ships as a Python/FastAPI service with a static web UI. For
judging, a packaged Windows executable removes the need to install Python or
run `pip install` — double-click `VeilShareEdge.exe`, the local server
starts, and the default browser opens the UI automatically.

## Option A — download the automated build (recommended for judges)

Every push to `main` triggers `.github/workflows/build-windows.yml`, which
builds `VeilShareEdge.exe` on a genuine Windows runner (GitHub Actions,
`windows-latest`) — not a cross-compiled or emulated build.

1. Open the repository's **Actions** tab on GitHub.
2. Select the latest successful **Build Windows executable** run.
3. Download the `VeilShareEdge-windows` artifact (a `.zip`).
4. Unzip it and run `VeilShareEdge.exe`.

A browser tab opens automatically at `http://127.0.0.1:8756`. Closing the
console window stops the app. No data leaves the machine — see
`docs/PRIVACY.md`.

## Option B — build it yourself on Windows

```powershell
git clone https://github.com/THEMIGHTYBULL/VeilShare-Edge.git
cd VeilShare-Edge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
python scripts\generate_demo_inputs.py
pyinstaller packaging\veilshare_edge.spec --noconfirm --clean
```

The executable and its bundled frontend/demo assets are written to
`dist\VeilShareEdge\VeilShareEdge.exe`. Copy the whole `dist\VeilShareEdge`
folder — the `.exe` depends on the sibling `_internal` runtime files
produced next to it (a "onedir" build, chosen over "onefile" so startup stays
fast — a single unpacking `.exe` adds several seconds of extraction on every
launch).

## What the packaged app includes / does not include

- Included: FastAPI backend, detection/redaction pipeline, static web UI,
  the four synthetic demo images and their OCR sidecars.
- Not included: EasyOCR / sentence-transformers model weights, or the
  `onnxruntime-qnn` execution provider. Those remain optional installs (see
  `models/README.md` and `requirements.txt`) so the base `.exe` stays small
  and every acceleration/engine claim on screen stays honest — the runtime
  panel reports `cpu-fallback` unless a real QNN provider is present on the
  machine running the `.exe`.

## Producing an .MSIX instead

Some challenge tracks additionally accept a `.msix` package. If required,
wrap the PyInstaller `dist\VeilShareEdge` output with the Windows
`MakeAppx.exe` tool (part of the Windows SDK) using a manifest declaring
`VeilShareEdge.exe` as the application executable. This is not automated in
CI because `.msix` packaging requires a code-signing certificate to install
without a SmartScreen warning; ask the challenge organizers whether an
unsigned `.msix` or the plain `.exe`/`.zip` is acceptable before investing in
signing infrastructure.
