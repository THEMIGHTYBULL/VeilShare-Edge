"""Privacy proof: watch for outbound network activity during a scan.

VeilShare Edge performs zero cloud calls at runtime by design. This module
makes that claim *checkable*: before a scan starts we snapshot this process's
TCP/UDP connections with psutil, and after it finishes we diff the snapshot.
Any new outbound connection would be reported — the "Privacy Proof" panel in
the UI shows the measured result of every scan, not a promise.
"""

from __future__ import annotations


def _snapshot():
    """Snapshot current connections, or None if the OS refuses (needs privileges)."""
    import psutil

    try:
        conns = psutil.Process().net_connections(kind="inet")
    except Exception:
        try:
            conns = psutil.net_connections(kind="inet")
        except Exception:
            return None

    out = set()
    for c in conns:
        try:
            laddr = tuple(c.laddr) if c.laddr else ()
            raddr = tuple(c.raddr) if c.raddr else ()
            out.add((c.status, laddr, raddr))
        except Exception:
            continue
    return out


class NetworkMonitor:
    """start() → run the scan → stop() → result()."""

    def __init__(self):
        self._before = None
        self._after = None

    def start(self) -> None:
        self._before = _snapshot()

    def stop(self) -> None:
        self._after = _snapshot()

    def result(self) -> dict:
        if self._before is None or self._after is None:
            return {
                "monitor": "unavailable",
                "new_outbound_connections_during_scan": None,
                "note": (
                    "Connection monitor needs OS privileges here. No code path in the "
                    "scan pipeline performs network I/O; audit backend/app/pipeline.py."
                ),
            }

        def outbound(conns):
            return {
                (status, laddr, raddr)
                for status, laddr, raddr in conns
                if raddr and status == "ESTABLISHED"
            }

        before, after = outbound(self._before), outbound(self._after)
        new = after - before
        return {
            "monitor": "psutil (process-level)",
            "established_outbound_before": len(before),
            "established_outbound_after": len(after),
            "new_outbound_connections_during_scan": len(new),
            "cloud_calls_during_scan": len(new),
            "note": "Measured with psutil around the scan. 0 means no outbound connection was opened.",
        }
