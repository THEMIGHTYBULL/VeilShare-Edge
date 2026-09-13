"""Deterministic sensitive-data detectors (regex + checksum + entropy).

Each detector receives one OCR text line and returns zero or more `Match`
objects carrying a character span. `scan_text()` runs every detector and
resolves overlaps so the most specific / most severe claim wins a span
(e.g. a JWT is labeled "JSON Web Token", not "high-entropy string").

Everything here is pure local string analysis: no network, no model weights.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, List

from .checksums import luhn_valid, verhoeff_valid

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def mask_secret(text: str) -> str:
    """Partially mask a secret for safe display (keeps first/last 4 chars)."""
    if len(text) <= 8:
        return "•" * len(text)
    keep = 4
    hidden = min(len(text) - 2 * keep, 10)
    return f"{text[:keep]}{'•' * hidden}{text[-keep:]}"


def shannon_entropy(s: str) -> float:
    """Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((v / n) * math.log2(v / n) for v in freq.values())


def _char_classes(s: str) -> int:
    """How many of the four character classes (lower/upper/digit/symbol) appear."""
    classes = 0
    if re.search(r"[a-z]", s):
        classes += 1
    if re.search(r"[A-Z]", s):
        classes += 1
    if re.search(r"\d", s):
        classes += 1
    if re.search(r"[^A-Za-z0-9]", s):
        classes += 1
    return classes


@dataclass
class Match:
    """A claimed sensitive span inside one OCR line."""

    start: int
    end: int
    category: str
    label: str
    severity: str
    text: str
    confidence: float
    explanation: str
    source: str = "regex"
    det_index: int = 0


# ---------------------------------------------------------------------------
# Detector implementations
# ---------------------------------------------------------------------------

def _det_aws_key(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b(AKIA[0-9A-Z]{16})\b", text):
        out.append(Match(m.start(1), m.end(1), "secret.aws_access_key", "AWS Access Key ID",
                         "critical", m.group(1), 0.97,
                         "Matches the AWS access key ID format (AKIA prefix + 16 uppercase alphanumerics)."))
    return out


def _det_aws_secret(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\baws[^\n]{0,30}secret[^\n]{0,10}[:=]\s*([A-Za-z0-9/+=]{40})\b")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "secret.aws_secret_key", "AWS Secret Access Key",
                         "critical", m.group(1), 0.95,
                         "40-character secret access key following an 'AWS secret' label."))
    return out


def _det_google_key(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b(AIza[0-9A-Za-z_\-]{35})\b", text):
        out.append(Match(m.start(1), m.end(1), "secret.google_api_key", "Google API Key",
                         "critical", m.group(1), 0.97,
                         "Matches the Google API key format (AIza prefix + 35 characters)."))
    return out


def _det_github_token(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b", text):
        out.append(Match(m.start(1), m.end(1), "secret.github_token", "GitHub Token",
                         "critical", m.group(1), 0.97,
                         "Matches the GitHub personal access / OAuth token format (gh?_ prefix)."))
    return out


def _det_slack_token(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b(xox[baprs]-[0-9A-Za-z\-]{10,})\b", text):
        out.append(Match(m.start(1), m.end(1), "secret.slack_token", "Slack Token",
                         "critical", m.group(1), 0.95,
                         "Matches the Slack token / webhook format (xox?- prefix)."))
    return out


def _det_openai_key(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b(sk-[A-Za-z0-9_\-]{20,})\b", text):
        out.append(Match(m.start(1), m.end(1), "secret.openai_key", "OpenAI-style API Key",
                         "critical", m.group(1), 0.95,
                         "Matches the OpenAI secret key format (sk- prefix)."))
    return out


def _det_jwt(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"\b(eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,})\b")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "secret.jwt", "JSON Web Token (JWT)",
                         "critical", m.group(1), 0.95,
                         "Three base64url segments starting with 'eyJ' — a JWT that may carry auth claims."))
    return out


def _det_private_key(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(-----BEGIN [A-Z ]{0,20}PRIVATE KEY-----)")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "secret.private_key", "Private Key Block",
                         "critical", m.group(1), 0.99,
                         "PEM private key header — the screen shows key material."))
    return out


def _det_cred_url(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"\b(https?://[^\s/:@]+:[^\s/@]+@[^\s]+)")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "secret.url_embedded_credentials", "URL with Embedded Credentials",
                         "critical", m.group(1), 0.95,
                         "URL contains a username:password pair before the host."))
    return out


def _det_api_key_param(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)[?&]((?:api_?key|access_?key|token|sig|signature|secret)=[^&\s]{6,})")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "secret.url_key_param", "Credential in URL Query",
                         "critical", m.group(1), 0.93,
                         "URL query parameter carries a credential (api key/token/signature)."))
    return out


def _det_password_assignment(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\b(pass(word)?|pwd|secret|token|api[_-]?key)\s*[:=]\s*([^\s]{6,})")
    for m in rx.finditer(text):
        out.append(Match(m.start(0), m.end(0), "secret.credential_assignment", "Credential Assignment",
                         "critical", m.group(0).strip(), 0.8,
                         "A password/secret/token label followed by a value — a live credential on screen."))
    return out


def _det_bearer(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._+/\-]{16,})")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "secret.bearer_token", "Bearer Token",
                         "critical", m.group(1), 0.92,
                         "HTTP Authorization bearer credential."))
    return out


def _det_card(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"\b((?:\d[ \-]?){12,18}\d)\b")
    for m in rx.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            out.append(Match(m.start(1), m.end(1), "payment.card_number", "Payment Card Number",
                             "critical", m.group(1), 0.99,
                             "13-19 digit number that passes the Luhn checksum — very likely a card number."))
    return out


def _det_cvv(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\b(cvv|cvc|security\s*code)\s*[:#]?\s*(\d{3,4})\b")
    for m in rx.finditer(text):
        out.append(Match(m.start(2), m.end(2), "payment.card_verification", "Card Verification Code",
                         "high", m.group(2), 0.9,
                         "3-4 digit CVV/CVC value — storing or showing CVV is high risk."))
    return out


def _det_ssn(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b(\d{3}-\d{2}-\d{4})\b", text):
        out.append(Match(m.start(1), m.end(1), "id.ssn_like", "SSN-like Identifier",
                         "high", m.group(1), 0.85,
                         "Matches the US Social Security Number format (NNN-NN-NNNN)."))
    return out


def _det_aadhaar(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?<!\d)(\d{4})[ \-]?(\d{4})[ \-]?(\d{4})(?!\d)")
    for m in rx.finditer(text):
        digits = m.group(1) + m.group(2) + m.group(3)
        if verhoeff_valid(digits):
            full = m.group(0)
            out.append(Match(m.start(0), m.end(0), "id.aadhaar_like", "Aadhaar-like Number",
                             "high", full, 0.93,
                             "12-digit number that passes the Verhoeff checksum used by Aadhaar."))
    return out


def _det_pan(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b([A-Z]{5}\d{4}[A-Z])\b", text):
        out.append(Match(m.start(1), m.end(1), "id.pan_like", "PAN-like Identifier",
                         "high", m.group(1), 0.85,
                         "Matches the Indian Permanent Account Number format (AAAAA9999A)."))
    return out


def _det_bank_account(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\b(account(?:\s*number)?|a/c(?:\s*no\.?)?|acct(?:\s*no\.?)?)\b[\s:#=]*((?:\d[ \-]?){8,17}\d)")
    for m in rx.finditer(text):
        out.append(Match(m.start(2), m.end(2), "payment.bank_account", "Bank Account Number",
                         "high", m.group(2), 0.9,
                         "Long digit run labelled as a bank account number."))
    return out


def _det_entropy_token(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b([A-Za-z0-9+/=_\-!@#$&*]{24,})\b", text):
        token = m.group(1)
        if shannon_entropy(token) >= 3.5 and _char_classes(token) >= 3:
            out.append(Match(m.start(1), m.end(1), "secret.high_entropy_token", "High-entropy Secret-like String",
                             "high", token, 0.7,
                             f"Long mixed-class string with entropy {shannon_entropy(token):.1f} bits/char — "
                             "looks like a generated secret, session token, or key."))
    return out


def _det_ifsc(text: str) -> List[Match]:
    out = []
    for m in re.finditer(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", text):
        out.append(Match(m.start(1), m.end(1), "payment.ifsc_like", "Bank Branch Code (IFSC-like)",
                         "medium", m.group(1), 0.8,
                         "Matches the Indian IFSC bank branch code format."))
    return out


def _det_upi(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"\b([a-z0-9][a-z0-9._\-]{1,}@(?:ok[a-z]{2,}|paytm|ybl|apl|ibl|axl))\b", re.I)
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "payment.upi_vpa", "UPI Virtual Payment Address",
                         "medium", m.group(1), 0.85,
                         "Looks like a UPI ID (name@bank) linked to a payment account."))
    return out


def _det_email(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "pii.email", "Email Address",
                         "medium", m.group(1), 0.92,
                         "Email address — personal contact information."))
    return out


def _det_phone_in(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?<!\d)(\+?91[\s\-]?)?([6-9]\d{4}[\s\-]?\d{5})(?!\d)")
    for m in rx.finditer(text):
        out.append(Match(m.start(0), m.end(0), "pii.phone_in", "Phone Number (India)",
                         "medium", m.group(0), 0.88,
                         "Matches an Indian mobile number format (optionally with +91 prefix)."))
    return out


def _det_phone_intl(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?<!\d)(\+\d{1,3}[\s\-.]?\(?\d{1,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4})(?!\d)")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "pii.phone_intl", "Phone Number",
                         "medium", m.group(1), 0.85,
                         "Matches an international phone number format."))
    return out


def _det_internal_url(text: str) -> List[Match]:
    out = []
    rx = re.compile(
        r"\b(https?://(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?::\d{1,5})?[^\s]*)"
    )
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "network.internal_url", "Internal/Private Network URL",
                         "medium", m.group(1), 0.85,
                         "URL points at a private network address — reveals internal infrastructure."))
    return out


def _det_student_id(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\bstudent\s*(?:id|no\.?|number)\s*[:=#]?\s*([A-Z0-9\-]{4,})")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "pii.student_id", "Student ID",
                         "medium", m.group(1), 0.85,
                         "Identifier labelled as a student ID number."))
    for m in re.finditer(r"\b(STU-\d{4,}(?:-\d{2,})?)\b", text, re.I):
        out.append(Match(m.start(1), m.end(1), "pii.student_id", "Student ID",
                         "medium", m.group(1), 0.85,
                         "Matches a STU-prefixed student identifier pattern."))
    return out


def _det_employee_id(text: str) -> List[Match]:
    out = []
    rx = re.compile(r"(?i)\bemployee\s*(?:id|no\.?|number)\s*[:=#]?\s*([A-Z0-9\-]{4,})")
    for m in rx.finditer(text):
        out.append(Match(m.start(1), m.end(1), "pii.employee_id", "Employee ID",
                         "medium", m.group(1), 0.85,
                         "Identifier labelled as an employee ID number."))
    return out


# Registry order encodes priority: earlier = more specific. Within a severity,
# earlier detectors claim overlapping spans first.
DETECTORS: List[Callable[[str], List[Match]]] = [
    _det_aws_key,            # critical
    _det_aws_secret,         # critical
    _det_google_key,         # critical
    _det_github_token,       # critical
    _det_slack_token,        # critical
    _det_openai_key,         # critical
    _det_jwt,                # critical
    _det_private_key,        # critical
    _det_cred_url,           # critical
    _det_api_key_param,      # critical
    _det_password_assignment,# critical (context-based)
    _det_bearer,             # critical
    _det_card,               # critical (Luhn-validated)
    _det_cvv,                # high
    _det_ssn,                # high
    _det_aadhaar,            # high (Verhoeff-validated)
    _det_pan,                # high
    _det_bank_account,       # high (context-based)
    _det_entropy_token,      # high
    _det_ifsc,               # medium
    _det_upi,                # medium
    _det_email,              # medium
    _det_phone_in,           # medium
    _det_phone_intl,         # medium
    _det_internal_url,       # medium
    _det_student_id,         # medium
    _det_employee_id,        # medium
]


def scan_text(text: str, bbox=None) -> List[dict]:
    """Scan one OCR line and return JSON-ready findings (most severe first)."""
    matches: List[Match] = []
    for idx, det in enumerate(DETECTORS):
        try:
            for m in det(text):
                m.det_index = idx
                matches.append(m)
        except Exception:  # a broken detector must never break a scan
            continue

    # Most severe first; within a severity, registry order (specificity) wins.
    matches.sort(key=lambda m: (SEVERITY_ORDER.get(m.severity, 9), m.det_index))

    claimed: List[tuple] = []
    chosen: List[Match] = []
    for m in matches:
        if any(not (m.end <= c0 or m.start >= c1) for c0, c1 in claimed):
            continue  # span already claimed by a stronger detector
        claimed.append((m.start, m.end))
        chosen.append(m)

    chosen.sort(key=lambda m: SEVERITY_ORDER.get(m.severity, 9))
    findings = []
    for i, m in enumerate(chosen, 1):
        findings.append({
            "id": f"F{i:02d}",
            "category": m.category,
            "label": m.label,
            "severity": m.severity,
            "text": m.text,
            "masked": mask_secret(m.text),
            "bbox": list(bbox) if bbox else None,
            "confidence": round(m.confidence, 3),
            "source": m.source,
            "explanation": m.explanation,
        })
    return findings


def scan_ocr_items(items) -> List[dict]:
    """Scan every OCR item; each item's bbox is attached to its findings."""
    findings: List[dict] = []
    for it in items:
        findings.extend(scan_text(it.text, bbox=it.bbox))
    return findings
