"""End-to-end API tests with FastAPI's TestClient (all local, no network)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def demo_ids():
    return [d["id"] for d in client.get("/api/demos").json()]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_runtime_reports_providers_honestly():
    r = client.get("/api/runtime")
    assert r.status_code == 200
    body = r.json()
    if body["onnxruntime"]:
        assert "available_providers" in body["onnxruntime"]
        assert body["acceleration_status"] in ("qnn-ready", "cpu-fallback")
        assert ("QNNExecutionProvider" in body["onnxruntime"]["available_providers"]) == \
               (body["acceleration_status"] == "qnn-ready")


def test_demos_listed(demo_ids):
    assert set(demo_ids) >= {"fake_dashboard", "fake_student_portal", "fake_invoice", "confidential_slide"}


def test_demo_image_served():
    r = client.get("/api/demos/fake_dashboard/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_scan_rejects_empty_request():
    assert client.post("/api/scan").status_code == 400


def test_scan_unknown_demo_404():
    r = client.post("/api/scan", data={"demo": "does_not_exist"})
    assert r.status_code == 404


def test_scan_demo_dashboard(demo_ids):
    r = client.post("/api/scan", data={"demo": "fake_dashboard"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"]["demo_id"] == "fake_dashboard"
    assert body["scan_id"]

    labels = {f["label"] for f in body["findings"]}
    assert "AWS Access Key ID" in labels
    assert "JSON Web Token (JWT)" in labels
    assert body["summary"]["by_severity"]["critical"] >= 4

    # honest engine reporting
    assert body["ocr_engine"] in ("easyocr", "simulated-sidecar", "none")
    assert body["semantic_engine"] in ("semantic-keyword-fallback", "semantic-minilm")

    # privacy proof: zero new outbound connections measured during the scan
    assert body["privacy"]["new_outbound_connections_during_scan"] == 0


def test_scan_confidential_slide_uses_semantics():
    r = client.post("/api/scan", data={"demo": "confidential_slide"})
    body = r.json()
    semantic_hits = [f for f in body["findings"] if f["category"] == "confidential.phrase"]
    assert len(semantic_hits) >= 4
    assert body["summary"]["by_severity"]["high"] >= 4


def test_scan_upload_bytes():
    # build a small image containing a planted secret
    from backend.app.demo_data import draw_fake_dashboard

    buf = io.BytesIO()
    draw_fake_dashboard().img.save(buf, format="PNG")
    r = client.post(
        "/api/scan",
        files={"file": ("dashboard.png", buf.getvalue(), "image/png")},
        data={"ocr": "simulated"},
    )
    assert r.status_code == 200
    # simulated OCR on an upload without sidecar → none engine, zero findings, honest note
    body = r.json()
    assert body["ocr_engine"] == "none"
    assert body["findings"] == []


def test_scan_upload_with_sidecar_path():
    # uploads normally rely on real OCR (easyocr) — if it is missing the scan
    # must still succeed and report engine "none" rather than failing.
    r = client.post(
        "/api/scan",
        files={"file": ("tiny.png", tiny_png(), "image/png")},
    )
    assert r.status_code == 200


def tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 30), "#ffffff").save(buf, format="PNG")
    return buf.getvalue()


def test_redact_flow():
    scan = client.post("/api/scan", data={"demo": "fake_dashboard"}).json()
    ids = [f["id"] for f in scan["findings"]][:2]
    r = client.post("/api/redact", json={
        "scan_id": scan["scan_id"], "mode": "blackout", "finding_ids": ids,
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(r.content))
    assert img.size == tuple(scan["image_size"])


def test_redact_bad_mode_400():
    scan = client.post("/api/scan", data={"demo": "fake_dashboard"}).json()
    r = client.post("/api/redact", json={"scan_id": scan["scan_id"], "mode": "frobnicate"})
    assert r.status_code == 400


def test_redact_unknown_scan_404():
    assert client.post("/api/redact", json={"scan_id": "nope", "mode": "blur"}).status_code == 404


def test_capture_graceful_without_mss():
    r = client.post("/api/capture")
    # 200 on machines with mss, 503 with a clear message elsewhere
    assert r.status_code in (200, 503)
    if r.status_code == 503:
        assert "mss" in r.json()["detail"]


def test_frontend_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "VeilShare Edge" in r.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200
