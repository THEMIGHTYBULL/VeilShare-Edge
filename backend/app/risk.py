"""Risk scoring: combine findings into an overall severity + score."""

from __future__ import annotations

from typing import Dict, List

# Points per finding by severity; capped at 100.
WEIGHTS = {"critical": 40, "high": 25, "medium": 10, "low": 4}


def summarize(findings: List[dict]) -> Dict:
    """Summarize a list of findings into counts, score, and worst severity."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        sev = f.get("severity", "low")
        if sev in counts:
            counts[sev] += 1

    overall = "none"
    for sev in ("critical", "high", "medium", "low"):
        if counts[sev] > 0:
            overall = sev
            break

    score = sum(WEIGHTS[sev] * n for sev, n in counts.items())
    return {
        "total_findings": len(findings),
        "by_severity": counts,
        "risk_score": min(100, score),
        "overall_severity": overall,
    }


def sort_findings(findings: List[dict]) -> List[dict]:
    """Order findings by severity, then top-to-bottom / left-to-right on screen."""
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def key(f: dict):
        bbox = f.get("bbox") or [0, 0, 0, 0]
        return (order.get(f.get("severity", "low"), 9), bbox[1], bbox[0])

    return sorted(findings, key=key)
