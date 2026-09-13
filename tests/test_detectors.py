"""Detector tests: every pattern that matters, plus overlap resolution."""

from backend.app.detectors import mask_secret, scan_ocr_items, scan_text, shannon_entropy
from backend.app.ocr import OCRItem


def find(text, category):
    hits = [f for f in scan_text(text) if f["category"] == category]
    return hits


def test_aws_access_key():
    hits = find("key: AKIAIOSFODNN7EXAMPLE ok", "secret.aws_access_key")
    assert len(hits) == 1 and hits[0]["severity"] == "critical"


def test_aws_secret_with_context():
    hits = find("AWS Secret Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "secret.aws_secret_key")
    assert len(hits) == 1
    # without context, the same 40 chars are still caught by the entropy detector
    hits2 = find("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "secret.high_entropy_token")
    assert len(hits2) == 1


def test_platform_tokens():
    assert find("ghp_Abc123Def456Ghi789Jkl012Mno345Pqr678St", "secret.github_token")
    # synthetic Slack token — concatenated so the literal never appears in a
    # committed text file (GitHub push protection cannot tell it is fake)
    slack = "xox" + "b-12345678-87654321-AbCdEfGhIjKlMnOpQrStUvWx"
    assert find(slack, "secret.slack_token")
    assert find("AIzaSyA1234567890abcdefghijklmnopqrstuv", "secret.google_api_key")
    assert find("sk-Abc123Def456Ghi789Jkl012", "secret.openai_key")


def test_jwt_wins_over_bearer_label():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vIn0.Xk9mQ2pVtR3nK8sL"
    hits = scan_text(f"auth: Bearer {jwt}")
    cats = [f["category"] for f in hits]
    assert "secret.jwt" in cats
    assert "secret.bearer_token" not in cats  # overlap resolved to the specific label
    assert "secret.credential_assignment" not in cats


def test_bearer_without_jwt_shape():
    hits = find("Authorization: Bearer abcdef1234567890abcdef", "secret.bearer_token")
    assert len(hits) == 1 and hits[0]["severity"] == "critical"


def test_card_number_luhn():
    hits = find("Card: 4111 1111 1111 1111", "payment.card_number")
    assert len(hits) == 1 and hits[0]["severity"] == "critical"
    # same length, wrong checksum → not a card
    assert find("Card: 4111 1111 1111 1112", "payment.card_number") == []
    # a bank-account context catches the failing-Luhn number instead
    hits = find("Account Number: 5010 0234 5678 91", "payment.bank_account")
    assert len(hits) == 1 and hits[0]["severity"] == "high"


def test_aadhaar_verhoeff_validated():
    from backend.app.checksums import verhoeff_check_digit

    partial = "23418567901"
    valid = partial + str(verhoeff_check_digit(partial))
    hits = find(f"Aadhaar: {valid[:4]} {valid[4:8]} {valid[8:]}", "id.aadhaar_like")
    assert len(hits) == 1 and hits[0]["severity"] == "high"
    # invalid checksum → not flagged as Aadhaar
    bad = valid[:-1] + ("0" if valid[-1] != "0" else "1")
    assert find(f"Aadhaar: {bad[:4]} {bad[4:8]} {bad[8:]}", "id.aadhaar_like") == []


def test_pan_and_ifsc():
    assert find("PAN: ABCDE1234F", "id.pan_like")
    assert find("IFSC: SBIN0001234", "payment.ifsc_like")
    # PAN regex must NOT fire inside a GSTIN
    assert find("GSTIN: 29ABCDE1234F1Z5", "id.pan_like") == []


def test_email_phone():
    assert find("contact: aarav.sharma@student.wbu.example", "pii.email")
    assert find("call +91 98765 43210", "pii.phone_in")
    assert find("office: +1 (415) 555-0132", "pii.phone_intl")


def test_upi_and_internal_url():
    assert find("pay: aarav@okbank", "payment.upi_vpa")
    assert find("see http://10.0.4.12:8080/grafana", "network.internal_url")
    assert find("see http://192.168.1.44:9000/minio", "network.internal_url")
    assert find("see https://acme.example.com/dashboard", "network.internal_url") == []


def test_student_and_employee_ids():
    hits = find("Student ID: STU-2024-018374", "pii.student_id")
    assert len(hits) == 1
    assert find("Employee ID: EMP-90241", "pii.employee_id")


def test_credential_in_url():
    hits = find("curl https://alice:s3cret@git.acme.example/repo", "secret.url_embedded_credentials")
    assert len(hits) == 1
    hits = find("fetch https://api.example.com/v1?api_key=abcdef1234567890abcdef", "secret.url_key_param")
    assert len(hits) == 1


def test_private_key_block():
    hits = find("-----BEGIN RSA PRIVATE KEY-----", "secret.private_key")
    assert len(hits) == 1 and hits[0]["severity"] == "critical"


def test_benign_text_is_clean():
    for text in [
        "Quarterly overview and next steps",
        "Total: Rs. 12,744.00",
        "CS201 Data Structures — B+",
        "CPU 34% MEM 61% Region ap-south-1",
        "Invoice No: INV-2024-0912",
    ]:
        assert scan_text(text) == [], text


def test_entropy_detector():
    assert find("Rotate: Xk9mQ2pVtR3nK8sLwYe7uFq1Zb", "secret.high_entropy_token")
    # low entropy or single-class strings are not flagged
    assert find("aaaaaaaaaaaaaaaaaaaaaaaaaaaa", "secret.high_entropy_token") == []
    assert find("abcdefghijklmnopqrstuvwxyz012345", "secret.high_entropy_token") == []


def test_mask_secret():
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "AKIA••••••••••MPLE"
    assert mask_secret("123456") == "••••••"


def test_scan_ocr_items_attaches_bbox():
    items = [OCRItem(text="key AKIAIOSFODNN7EXAMPLE here", bbox=(10, 20, 200, 30), confidence=1.0)]
    findings = scan_ocr_items(items)
    assert findings and findings[0]["bbox"] == [10, 20, 200, 30]


def test_shannon_entropy():
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("ab") == 1.0
    assert shannon_entropy("abcdefgh") == 3.0
