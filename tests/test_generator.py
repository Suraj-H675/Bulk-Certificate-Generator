from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.pdfgen import canvas

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


def test_long_recipient_name_fits_within_template_width():
    pdf = canvas.Canvas(BytesIO())
    max_width = 660

    font_size, lines = PdfCertificateGenerator._fit_lines(
        pdf,
        "W" * 200,
        font_name="Helvetica-Bold",
        max_font_size=30,
        min_font_size=10,
        max_width=max_width,
        max_lines=3,
    )

    assert len(lines) <= 3
    assert all(
        pdf.stringWidth(line, "Helvetica-Bold", font_size) <= max_width
        for line in lines
    )
