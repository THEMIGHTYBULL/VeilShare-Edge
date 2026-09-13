"""Risk summary tests."""

from backend.app.risk import sort_findings, summarize


def test_empty():
    s = summarize([])
    assert s["overall_severity"] == "none"
    assert s["risk_score"] == 0
    assert s["total_findings"] == 0


def test_worst_severity_wins():
    s = summarize([
        {"severity": "medium"},
        {"severity": "critical"},
        {"severity": "high"},
    ])
    assert s["overall_severity"] == "critical"
    assert s["by_severity"] == {"critical": 1, "high": 1, "medium": 1, "low": 0}


def test_score_weights_and_cap():
    s = summarize([{"severity": "critical"}] * 3)  # 120 → capped at 100
    assert s["risk_score"] == 100
    s = summarize([{"severity": "high"}, {"severity": "medium"}])
    assert s["risk_score"] == 35


def test_sort_by_severity_then_position():
    findings = [
        {"id": "a", "severity": "medium", "bbox": [10, 10, 5, 5]},
        {"id": "b", "severity": "critical", "bbox": [50, 90, 5, 5]},
        {"id": "c", "severity": "critical", "bbox": [20, 40, 5, 5]},
    ]
    order = [f["id"] for f in sort_findings(findings)]
    assert order == ["c", "b", "a"]
