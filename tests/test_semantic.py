"""Semantic engine tests (keyword fallback runs everywhere; MiniLM is optional)."""

from backend.app.ocr import OCRItem
from backend.app.semantic import analyze, minilm_available


def items(*texts):
    return [OCRItem(text=t, bbox=(0, i * 20, 100, 18), confidence=1.0) for i, t in enumerate(texts)]


def test_confidential_phrases_flagged():
    findings, engine = analyze(items(
        "Internal roadmap: Project Veil ships November",
        "Salary revision sheet attached",
        "This deck is confidential",
    ))
    assert len(findings) == 3
    assert all(f["severity"] == "high" for f in findings)
    assert all(f["category"] == "confidential.phrase" for f in findings)
    assert findings[0]["source"] == "semantic-keyword" or findings[0]["source"] == "semantic-minilm"
    assert engine in ("semantic-keyword-fallback", "semantic-minilm")


def test_benign_text_not_flagged():
    findings, _ = analyze(items("Quarterly overview", "Agenda: kickoff at 10am"))
    assert findings == []


def test_bboxes_carried_through():
    findings, _ = analyze(items("do not share this"))
    assert findings[0]["bbox"] == [0, 0, 100, 18]


def test_minilm_availability_reported_consistently():
    # Whichever engine is reported must match what actually ran.
    findings, engine = analyze(items("confidential"))
    if minilm_available():
        assert engine == "semantic-minilm"
    else:
        assert engine == "semantic-keyword-fallback"
