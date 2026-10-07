from __future__ import annotations

from datetime import date

from bulk_certificate_generator.generator import PdfCertificateGenerator


def test_generator_returns_real_pdf_with_recipient_content():
    content = PdfCertificateGenerator().generate(
        title="Certificate of Completion",
        event_name="Backend Workshop",
        issue_date=date(2026, 10, 8),
        recipient_name="Alice Example",
        certificate_id="certificate-123",
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 1000
    assert b"Alice Example" in content
    assert b"Backend Workshop" in content
