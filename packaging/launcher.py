"""Desktop launcher for the packaged VeilShare Edge executable.

This is the entry point PyInstaller bundles into VeilShareEdge.exe. It starts
the same FastAPI app used in `backend/app/main.py`, binds to localhost only
(privacy-first: no LAN exposure), and opens the default browser once the
server is ready — so a judge can double-click one .exe and get a working UI
with no terminal, no `pip install`, and no manual steps.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# When frozen by PyInstaller, resources are unpacked next to sys._MEIPASS.
if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VEILSHARE_HOST", "127.0.0.1")
os.environ.setdefault("VEILSHARE_PORT", "8756")


def _open_browser_when_ready(url: str, timeout: float = 15.0) -> None:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(0.25)
    # Open anyway; the server may just be slow to answer the very first probe.
    webbrowser.open(url)


def main() -> None:
    import uvicorn

    from backend.app.main import app

    host = os.environ["VEILSHARE_HOST"]
    port = int(os.environ["VEILSHARE_PORT"])
    url = f"http://{host}:{port}"

    print("=" * 62)
    print(" VeilShare Edge — on-device privacy firewall")
    print(f" Local UI: {url}")
    print(" All scanning happens on this machine. Nothing is uploaded.")
    print(" Close this window to stop the app.")
    print("=" * 62)

    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
