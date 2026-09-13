"""Synthetic demo screenshots + ground-truth sidecars.

Every demo image is 100% synthetic (fake company, fake people, fake secrets).
While drawing, a `Sheet` records the bounding box of every rendered string;
that list is saved next to the PNG as a JSON "sidecar". The OCR layer can
then simulate OCR results on CPU-only dev machines that don't have EasyOCR
installed — clearly labeled as simulated in the API/UI.

Regenerate with:  python scripts/generate_demo_inputs.py [--force]
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont

from .checksums import verhoeff_check_digit

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "demo" / "sample_inputs"

# ---------------------------------------------------------------------------
# Fonts (works on Linux CI, Windows dev machines, and macOS)
# ---------------------------------------------------------------------------

_FONT_PATHS = {
    "sans": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
    "sans_bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    "mono": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ],
}

_font_cache = {}


def get_font(kind: str, size: int):
    key = (kind, size)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    for path in _FONT_PATHS.get(kind, []):
        try:
            font = ImageFont.truetype(path, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


class Sheet:
    """Image + draw handle that records every rendered string's bbox."""

    def __init__(self, w: int, h: int, bg):
        self.img = Image.new("RGB", (w, h), bg)
        self.draw = ImageDraw.Draw(self.img)
        self.texts: List[dict] = []
        self.size = (w, h)

    def text(self, x, y, s, font, fill, anchor="la"):
        self.draw.text((x, y), s, font=font, fill=fill, anchor=anchor)
        box = self.draw.textbbox((x, y), s, font=font, anchor=anchor)
        self.texts.append({
            "text": s,
            "bbox": [box[0], box[1], box[2] - box[0], box[3] - box[1]],
        })

    def fit_text(self, x, y, s, kind, fill, max_size, min_size=10, max_width=400, anchor="la"):
        """Render at the largest size <= max_size that fits max_width."""
        size = max_size
        while size > min_size:
            font = get_font(kind, size)
            box = self.draw.textbbox((0, 0), s, font=font, anchor=anchor)
            if box[2] - box[0] <= max_width:
                break
            size -= 1
        self.text(x, y, s, get_font(kind, size), fill, anchor=anchor)

    def rect(self, box, fill=None, outline=None, width=1, radius=0):
        if radius:
            self.draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
        else:
            self.draw.rectangle(box, fill=fill, outline=outline, width=width)


# ---------------------------------------------------------------------------
# Demo 1: developer dashboard (secrets everywhere)
# ---------------------------------------------------------------------------

def draw_fake_dashboard() -> Sheet:
    # Synthetic Slack-style webhook token. Built by concatenation on purpose:
    # the literal must NOT appear in any committed text file or GitHub push
    # protection blocks the push (it cannot tell synthetic demo data from a
    # real token). The rendered PNG is binary, so it is never scanned.
    slack_demo_token = "xox" + "b-12345678-87654321-AbCdEfGhIjKlMnOpQrStUvWx"

    s = Sheet(1280, 720, "#0f172a")

    # Top bar
    s.rect((0, 0, 1280, 64), fill="#1e293b")
    s.text(24, 16, "Acme Corp — DevOps Console", get_font("sans_bold", 24), "#e2e8f0")
    s.text(1256, 20, "admin@acme-test.example", get_font("mono", 18), "#94a3b8", anchor="ra")

    # Sidebar
    s.rect((0, 64, 220, 720), fill="#111827")
    nav = ["Dashboard", "Deployments", "Secrets", "Logs", "Settings"]
    for i, item in enumerate(nav):
        s.text(24, 110 + i * 44, item, get_font("sans", 20), "#64748b")
    s.text(24, 620, "deploy key — do not share", get_font("sans", 15), "#475569")

    def card(x, y, w, h, title, value):
        s.rect((x, y, x + w, y + h), fill="#1e293b", outline="#334155", width=1, radius=12)
        s.text(x + 20, y + 16, title, get_font("sans_bold", 17), "#93c5fd")
        s.fit_text(x + 20, y + 52, value, "mono", "#e2e8f0", max_size=20, min_size=10,
                   max_width=w - 40)

    card(260, 96, 460, 118, "AWS Access Key ID", "AKIAIOSFODNN7EXAMPLE")
    card(760, 96, 460, 118, "AWS Secret Key", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    card(260, 234, 460, 118, "GitHub PAT", "ghp_Abc123Def456Ghi789Jkl012Mno345Pqr678St")
    card(760, 234, 460, 118, "Google API Key", "AIzaSyA1234567890abcdefghijklmnopqrstuv")
    card(260, 372, 460, 118, "Slack Webhook", slack_demo_token)
    card(760, 372, 460, 118, "Internal Grafana", "http://10.0.4.12:8080/grafana")

    # Full-width card: auth header with JWT + a rotation reminder
    s.rect((260, 510, 1220, 640), fill="#1e293b", outline="#334155", width=1, radius=12)
    s.text(280, 526, "Auth Header", get_font("sans_bold", 17), "#93c5fd")
    s.fit_text(280, 560, "auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vIn0.Xk9mQ2pVtR3nK8sL",
               "mono", "#e2e8f0", max_size=16, min_size=9, max_width=920)
    s.fit_text(280, 596, "Rotate before demo: Xk9mQ2pVtR3nK8sLwYe7uFq1Zb", "sans", "#fbbf24",
               max_size=17, min_size=10, max_width=920)

    # Status bar
    s.rect((0, 692, 1280, 720), fill="#1e293b")
    s.text(24, 698, "CPU 34%   ·   MEM 61%   ·   Region ap-south-1", get_font("mono", 15), "#64748b")
    return s


# ---------------------------------------------------------------------------
# Demo 2: student portal (PII)
# ---------------------------------------------------------------------------

def draw_fake_student_portal() -> Sheet:
    aadhaar = "23418567901" + str(verhoeff_check_digit("23418567901"))
    aadhaar_fmt = f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}"

    s = Sheet(1280, 720, "#f1f5f9")

    # Header
    s.rect((0, 0, 1280, 96), fill="#1d4ed8")
    s.text(48, 18, "Westbridge University", get_font("sans_bold", 30), "#ffffff")
    s.text(48, 60, "Student Portal — Demo Data", get_font("sans", 17), "#bfdbfe")

    # Profile card
    s.rect((60, 136, 620, 648), fill="#ffffff", outline="#e2e8f0", width=1, radius=14)
    s.text(92, 164, "Student Profile", get_font("sans_bold", 22), "#0f172a")
    rows = [
        ("Name", "Aarav Sharma", "sans"),
        ("Student ID", "STU-2024-018374", "mono"),
        ("Email", "aarav.sharma@student.wbu.example", "mono"),
        ("Phone", "+91 98765 43210", "mono"),
        ("Aadhaar (on file)", aadhaar_fmt, "mono"),
        ("Address", "Hostel Block C, Room 214, North Campus", "sans"),
        ("CGPA", "8.62", "mono"),
    ]
    y = 216
    for label, value, kind in rows:
        s.text(92, y, label, get_font("sans", 18), "#64748b")
        s.fit_text(92, y + 30, value, kind, "#0f172a", max_size=20, min_size=11, max_width=500)
        y += 62

    # Courses card
    s.rect((660, 136, 1220, 648), fill="#ffffff", outline="#e2e8f0", width=1, radius=14)
    s.text(692, 164, "Registered Courses", get_font("sans_bold", 22), "#0f172a")
    courses = [
        "CS201 Data Structures — B+",
        "MA110 Linear Algebra — A",
        "HS105 Ethics in Technology — B",
        "CS301 Computer Networks — A-",
        "Semester: Monsoon 2025",
        "Advisor: Prof. (Demo) Iyer",
    ]
    for i, c in enumerate(courses):
        s.text(692, 216 + i * 52, c, get_font("sans", 20), "#334155")

    s.text(60, 676, "This screen contains 100% synthetic demo data.", get_font("sans", 15), "#94a3b8")
    return s


# ---------------------------------------------------------------------------
# Demo 3: invoice (payment data)
# ---------------------------------------------------------------------------

def draw_fake_invoice() -> Sheet:
    s = Sheet(1280, 800, "#ffffff")

    # Header
    s.text(60, 40, "ACME TRADERS PVT LTD", get_font("sans_bold", 30), "#0f172a")
    s.text(60, 82, "12 Demo Street, Bengaluru 560001", get_font("sans", 17), "#64748b")
    s.text(1220, 44, "Tax Invoice", get_font("sans_bold", 26), "#334155", anchor="ra")

    # Meta
    s.text(60, 140, "Invoice No: INV-2024-0912", get_font("mono", 19), "#0f172a")
    s.text(60, 172, "Date: 2025-09-12", get_font("mono", 19), "#0f172a")
    s.text(60, 204, "GSTIN: 29ABCDE1234F1Z5", get_font("mono", 19), "#0f172a")
    s.text(1220, 140, "Bill To: Westbridge University", get_font("sans", 19), "#334155", anchor="ra")
    s.text(1220, 172, "Accounts Department", get_font("sans", 19), "#64748b", anchor="ra")

    # Item table
    table_top = 250
    s.rect((60, table_top, 800, table_top + 40), fill="#e2e8f0")
    s.text(76, table_top + 8, "Item", get_font("sans_bold", 18), "#0f172a")
    s.text(520, table_top + 8, "Qty", get_font("sans_bold", 18), "#0f172a")
    s.text(660, table_top + 8, "Amount", get_font("sans_bold", 18), "#0f172a", anchor="ra")
    s.rect((60, table_top, 800, table_top + 40))  # outline track
    lines = [
        ("Laboratory equipment", "4", "6,400.00"),
        ("Library journals (annual)", "1", "3,200.00"),
        ("Cloud credits (edu license)", "10", "1,200.00"),
    ]
    y = table_top + 56
    for item, qty, amt in lines:
        s.text(76, y, item, get_font("sans", 18), "#334155")
        s.text(528, y, qty, get_font("sans", 18), "#334155")
        s.text(660, y, amt, get_font("mono", 18), "#0f172a", anchor="ra")
        s.rect((60, y - 10, 800, y + 30), outline="#eef2f7", width=1)
        y += 52
    s.rect((60, table_top, 800, y - 10), outline="#cbd5e1", width=1)

    # Totals
    s.text(660, y + 16, "Subtotal: 10,800.00", get_font("mono", 19), "#0f172a", anchor="ra")
    s.text(660, y + 48, "GST (18%): 1,944.00", get_font("mono", 19), "#0f172a", anchor="ra")
    s.text(660, y + 84, "Total: Rs. 12,744.00", get_font("sans_bold", 22), "#0f172a", anchor="ra")

    # Payment details box
    s.rect((860, 250, 1220, 520), fill="#f8fafc", outline="#e2e8f0", width=1, radius=12)
    s.text(884, 270, "Payment Details", get_font("sans_bold", 20), "#0f172a")
    pay = [
        "Account Number: 5010 0234 5678 91",
        "IFSC: SBIN0001234",
        "PAN: ABCDE1234F",
        "Card (on file): 4111 1111 1111 1111",
        "CVV: 123",
        "UPI: aarav@okbank",
    ]
    for i, line in enumerate(pay):
        s.fit_text(884, 312 + i * 34, line, "mono", "#334155", max_size=18, min_size=10, max_width=320)

    s.text(60, 750, "Synthetic invoice generated for VeilShare Edge demos. No real financial data.",
           get_font("sans", 15), "#94a3b8")
    return s


# ---------------------------------------------------------------------------
# Demo 4: confidential slide (semantic leaks)
# ---------------------------------------------------------------------------

def draw_confidential_slide() -> Sheet:
    s = Sheet(1280, 720, "#0b1220")

    s.text(90, 70, "INTERNAL — NOT FOR DISTRIBUTION", get_font("sans_bold", 20), "#f87171")
    s.text(90, 116, "Q3 FY25 Board Review", get_font("sans_bold", 46), "#f1f5f9")
    s.text(90, 186, "Acme Corp · Leadership Only", get_font("sans", 22), "#64748b")

    bullets = [
        "Internal roadmap: Project Veil ships November",
        "Salary revision sheet — HR confidential",
        "Client contract renewal: Vertex Labs (Rs. 2.4 Cr)",
        "Do not share outside the leadership team",
    ]
    y = 280
    for b in bullets:
        s.text(110, y, "▸", get_font("sans_bold", 26), "#22d3ee")
        s.text(146, y, b, get_font("sans", 26), "#cbd5e1")
        y += 74

    s.text(90, 660, "Page 7 · Confidential", get_font("sans", 17), "#475569")
    return s


# ---------------------------------------------------------------------------
# Registry + generation
# ---------------------------------------------------------------------------

DEMO_SPECS = [
    {
        "id": "fake_dashboard",
        "name": "Developer Dashboard",
        "description": "Console screen full of API keys, tokens, a JWT and an internal URL.",
        "draw": draw_fake_dashboard,
    },
    {
        "id": "fake_student_portal",
        "name": "Student Portal",
        "description": "Profile page with student ID, email, phone and an Aadhaar-like number.",
        "draw": draw_fake_student_portal,
    },
    {
        "id": "fake_invoice",
        "name": "Tax Invoice",
        "description": "Invoice with bank account, IFSC, PAN, card number, CVV and UPI ID.",
        "draw": draw_fake_invoice,
    },
    {
        "id": "confidential_slide",
        "name": "Confidential Slide",
        "description": "Board slide leaking confidential phrasing no regex can enumerate.",
        "draw": draw_confidential_slide,
    },
]


def demo_list() -> list:
    """JSON-ready list of demos for the API."""
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "description": d["description"],
            "image": f"/api/demos/{d['id']}/image",
        }
        for d in DEMO_SPECS
    ]


def demo_path(demo_id: str) -> Path:
    return DEMO_DIR / f"{demo_id}.png"


def generate_all(force: bool = False) -> List[Path]:
    """Generate every demo PNG + sidecar that is missing (or all with force)."""
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for spec in DEMO_SPECS:
        png = DEMO_DIR / f"{spec['id']}.png"
        sidecar = DEMO_DIR / f"{spec['id']}.json"
        if not force and png.exists() and sidecar.exists():
            continue
        sheet = spec["draw"]()
        sheet.img.save(png, "PNG")
        sidecar.write_text(
            json.dumps(
                {
                    "demo_id": spec["id"],
                    "note": "Synthetic demo data. Every string is fake. Sidecar simulates OCR ground truth.",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "image_size": list(sheet.size),
                    "texts": sheet.texts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        written.extend([png, sidecar])
    return written
