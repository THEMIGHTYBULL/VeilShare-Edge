"""Semantic sensitivity analysis for OCR text.

Two engines, selected at runtime:

1. **MiniLM semantic engine** — uses `sentence-transformers` with an
   all-MiniLM-L6-v2-style encoder when the package is installed. Text is
   embedded and compared against anchor phrases describing confidential
   content; cosine similarity above a threshold is flagged.

2. **Keyword fallback engine** — deterministic keyword/phrase matching used
   when no semantic model is available (CPU-only dev machines, minimal
   installs). Honest labeling: the response always reports which engine ran.

Rules catch obvious secrets; semantic analysis catches *meaning-based* leaks
("internal roadmap", "salary sheet", "do not share") that no regex can list
exhaustively.
"""

from __future__ import annotations

from typing import List, Tuple

from .detectors import mask_secret

# Keyword fallback rules: (compiled phrase regex, explanation phrase)
KEYWORD_RULES = [
    ("confidential", "confidentiality marker"),
    (r"internal\s+roadmap", "internal planning content"),
    (r"do\s+not\s+(share|distribute)", "distribution restriction"),
    (r"not\s+for\s+distribution", "distribution restriction"),
    (r"internal\s+only", "internal-only marker"),
    (r"employee\s+only", "employee-only marker"),
    (r"\bsalary\b|\bpayroll\b|\bcompensation\b", "HR/compensation data"),
    (r"client\s+contract|contract\s+renewal", "commercial contract content"),
    (r"board\s+(deck|review|minutes)", "board-level material"),
    (r"proprietary|trade\s+secret", "proprietary content marker"),
    (r"\bnda\b", "NDA reference"),
    (r"unreleased|embargo", "pre-release content marker"),
]

# Anchors for the MiniLM engine: text semantically close to these is flagged.
CONF_ANCHORS = [
    "confidential internal document, not to be shared externally",
    "private personal information of an individual",
    "secret credentials and access keys",
    "salary and compensation details of employees",
    "internal roadmap and unreleased product plans",
    "legal contract between the company and a client",
]

SIM_THRESHOLD = 0.55


def _keyword_engine(items) -> Tuple[List[dict], str]:
    import re

    findings: List[dict] = []
    for idx, it in enumerate(items, 1):
        hits = []
        for pattern, label in KEYWORD_RULES:
            if re.search(pattern, it.text, re.IGNORECASE):
                hits.append(label)
        if not hits:
            continue
        findings.append({
            "id": f"S{idx:02d}",
            "category": "confidential.phrase",
            "label": "Confidential Content",
            "severity": "high",
            "text": it.text,
            "masked": mask_secret(it.text),
            "bbox": list(it.bbox) if it.bbox else None,
            "confidence": 0.8,
            "source": "semantic-keyword",
            "explanation": f"Semantic engine (keyword fallback) matched: {', '.join(sorted(set(hits)))}.",
        })
    return findings, "semantic-keyword-fallback"


def _minilm_engine(items) -> Tuple[List[dict], str]:
    from sentence_transformers import SentenceTransformer, util

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    anchor_emb = model.encode(CONF_ANCHORS, convert_to_tensor=True)
    findings: List[dict] = []
    for idx, it in enumerate(items, 1):
        emb = model.encode(it.text, convert_to_tensor=True)
        sims = util.cos_sim(emb, anchor_emb)[0]
        best = float(sims.max())
        if best >= SIM_THRESHOLD:
            findings.append({
                "id": f"S{idx:02d}",
                "category": "confidential.phrase",
                "label": "Confidential Content",
                "severity": "high",
                "text": it.text,
                "masked": mask_secret(it.text),
                "bbox": list(it.bbox) if it.bbox else None,
                "confidence": round(best, 3),
                "source": "semantic-minilm",
                "explanation": (
                    f"MiniLM semantic similarity {best:.2f} to confidential-content anchors "
                    f"(threshold {SIM_THRESHOLD})."
                ),
            })
    return findings, "semantic-minilm"


def minilm_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def analyze(items) -> Tuple[List[dict], str]:
    """Run the best available semantic engine over OCR items.

    Returns (findings, engine_name). Engine name is reported verbatim in API
    responses so the demo never overstates which AI actually ran.
    """
    if minilm_available():
        try:
            return _minilm_engine(items)
        except Exception:
            pass  # fall through to keyword engine on any model-load failure
    return _keyword_engine(items)
