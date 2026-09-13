# Demo Sample Inputs

Four **100% synthetic** screenshots for demonstrating and testing VeilShare
Edge. Fake company, fake people, fake secrets — never add real data here.

| File | Shows |
|---|---|
| `fake_dashboard.png` | Console with API keys, PATs, a JWT, an internal URL (secrets) |
| `fake_student_portal.png` | Student profile: ID, email, phone, Aadhaar-like number (PII) |
| `fake_invoice.png` | Bank account, IFSC, PAN, Luhn-valid card, CVV, UPI (payment) |
| `confidential_slide.png` | Board slide with confidential phrasing (semantic leaks) |

The `*.json` sidecars (OCR ground truth used to simulate OCR on machines
without EasyOCR) are **generated on first boot** — the server, the test
suite, and the benchmark harness all create them automatically. To regenerate
by hand:

```bash
python scripts/generate_demo_inputs.py --force
```

Sidecars are git-ignored on purpose: they contain synthetic token strings
that GitHub push protection cannot distinguish from real secrets.
