"""VeilShare Edge API + local web UI.

Run from the repository root:

    python backend/app/main.py                 # script mode
    python -m uvicorn backend.app.main:app     # app mode

The server binds to 127.0.0.1 by default (privacy-first: no LAN exposure).
Override with VEILSHARE_HOST / VEILSHARE_PORT for remote dev containers.
"""

from __future__ import annotations

import io
import os
import sys
import threading
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from backend.app import __version__, demo_data, pipeline
from backend.app.capture import capture_screen
from backend.app.redact import MODES, redact_findings

FRONTEND_DIR = ROOT / "frontend"


# --------------------------------------------------------------------------
# In-memory scan store (raw pixels are never written to disk)
# --------------------------------------------------------------------------

class ScanStore:
    """Keeps the last N scans in memory so redaction can reference them.

    Nothing here is persisted: restarting the server wipes every screenshot,
    which is exactly the privacy behavior we promise.
    """

    def __init__(self, capacity: int = 32):
        self._items: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = threading.Lock()
        self._capacity = capacity

    def add(self, image: Image.Image, result: dict) -> str:
        scan_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._items[scan_id] = {"image": image, "result": result}
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)
        return scan_id

    def get(self, scan_id: str):
        with self._lock:
            return self._items.get(scan_id)


SCANS = ScanStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    demo_data.generate_all()  # make sure demo inputs exist on first boot
    yield


app = FastAPI(
    title="VeilShare Edge",
    version=__version__,
    description="On-device privacy firewall for screen sharing and screenshots. Local-only by design.",
    lifespan=lifespan,
)


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "VeilShare Edge", "version": __version__}


@app.get("/api/runtime")
def runtime():
    from backend.app.runtime_info import runtime_panel

    return runtime_panel()


@app.get("/api/demos")
def demos():
    demo_data.generate_all()
    return demo_data.demo_list()


@app.get("/api/demos/{demo_id}/image")
def demo_image(demo_id: str):
    path = demo_data.demo_path(demo_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"unknown demo '{demo_id}'")
    return FileResponse(path, media_type="image/png")


def _load_upload(file: UploadFile) -> Image.Image:
    try:
        return Image.open(file.file).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"could not read image: {exc}") from exc


def _scan_and_store(image: Image.Image, demo_id=None, prefer_ocr="auto") -> dict:
    result = pipeline.run_scan(image, demo_id=demo_id, prefer_ocr=prefer_ocr)
    scan_id = SCANS.add(image, result)
    return {
        "scan_id": scan_id,
        "source": {"type": "demo" if demo_id else "upload", "demo_id": demo_id},
        **result,
    }


@app.post("/api/scan")
async def scan(
    file: UploadFile | None = File(None),
    demo: str | None = Form(None),
    ocr: str = Form("auto"),
):
    """Scan an uploaded image or a built-in demo screenshot. Runs fully locally."""
    if file is not None:
        image = _load_upload(file)
        return _scan_and_store(image, demo_id=None, prefer_ocr=ocr)
    if demo:
        path = demo_data.demo_path(demo)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"unknown demo '{demo}'")
        image = Image.open(path).convert("RGB")
        return _scan_and_store(image, demo_id=demo, prefer_ocr=ocr)
    raise HTTPException(status_code=400, detail="provide an image 'file' or a 'demo' id")


@app.post("/api/capture")
async def capture(
    monitor: int = Form(0),
    x: int | None = Form(None),
    y: int | None = Form(None),
    w: int | None = Form(None),
    h: int | None = Form(None),
    ocr: str = Form("auto"),
):
    """Capture the screen (or a region) and scan it. Requires the optional 'mss' package."""
    region = (x, y, w, h) if None not in (x, y, w, h) else None
    try:
        image = capture_screen(monitor_index=monitor, region=region)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _scan_and_store(image, demo_id=None, prefer_ocr=ocr)


@app.post("/api/redact")
def redact(body: dict):
    """Create the Safe Share image for a scan.

    Body: {"scan_id": "...", "mode": "blur"|"blackout"|"pixelate",
           "finding_ids": ["F01", ...]  // optional; defaults to all findings}
    """
    scan_id = body.get("scan_id")
    mode = body.get("mode", "blur")
    if mode not in MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {MODES}")
    entry = SCANS.get(scan_id) if scan_id else None
    if entry is None:
        raise HTTPException(status_code=404, detail="scan not found (it may have expired)")

    findings = entry["result"]["findings"]
    finding_ids = body.get("finding_ids")
    if finding_ids is not None and not isinstance(finding_ids, list):
        raise HTTPException(status_code=400, detail="finding_ids must be a list")
    redacted = redact_findings(entry["image"], findings, mode=mode, finding_ids=finding_ids)

    buf = io.BytesIO()
    redacted.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# --------------------------------------------------------------------------
# Static frontend (must be mounted last so /api routes win)
# --------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("VEILSHARE_HOST", "127.0.0.1")
    port = int(os.environ.get("VEILSHARE_PORT", "8000"))
    print(f"VeilShare Edge → http://{host}:{port}  (local-only by default)")
    uvicorn.run(app, host=host, port=port)
