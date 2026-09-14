# Assets

UI evidence for the submission README and demo materials.

```text
assets/
└── screenshots/
    ├── dashboard_risk_overlay.png            # fake_dashboard.png scan: bounding boxes + severity labels
    ├── dashboard_safe_share_blur.png         # same scan, Safe Share (blur mode)
    ├── dashboard_safe_share_blackout.png     # same scan, Safe Share (blackout mode)
    ├── dashboard_safe_share_pixelate.png     # same scan, Safe Share (pixelate mode)
    ├── fake_invoice_risk_overlay.png         # fake_invoice.png scan: bounding boxes + severity labels
    ├── fake_invoice_safe_share.png           # same scan, Safe Share (blur)
    ├── fake_student_portal_risk_overlay.png  # fake_student_portal.png scan: bounding boxes + severity labels
    ├── fake_student_portal_safe_share.png    # same scan, Safe Share (blur)
    ├── confidential_slide_risk_overlay.png   # confidential_slide.png scan: bounding boxes + severity labels
    └── confidential_slide_safe_share.png     # same scan, Safe Share (blur)
```

All screenshots above are **real output** of `backend/app/pipeline.run_scan`
and `backend/app/redact.redact_findings`, generated directly from this
repository's demo inputs — not mockups. Regenerate them at any time with:

```bash
python -m pytest tests/ -q   # sanity check first
python - <<'PY'
# see docs/DEMO_SCRIPT.md for the full walkthrough; the same pipeline calls
# used to produce these screenshots are shown there.
PY
```

Every image shows only synthetic demo data (fake company, fake people, fake
secrets) — see `demo/sample_inputs/README.md`.
