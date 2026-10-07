from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


class PdfCertificateGenerator:
    def generate(
        self,
        *,
        title: str,
        event_name: str,
        issue_date: date,
        recipient_name: str,
        certificate_id: str,
    ) -> bytes:
        buffer = BytesIO()
        page_width, page_height = landscape(A4)
        pdf = canvas.Canvas(
            buffer,
            pagesize=(page_width, page_height),
            pageCompression=0,
        )

        margin = 34
        pdf.setLineWidth(2)
        pdf.rect(margin, margin, page_width - 2 * margin, page_height - 2 * margin)
        pdf.setLineWidth(0.7)
        pdf.rect(margin + 8, margin + 8, page_width - 2 * (margin + 8), page_height - 2 * (margin + 8))

        pdf.setFont("Helvetica-Bold", 30)
        pdf.drawCentredString(page_width / 2, page_height - 120, title)
        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(page_width / 2, page_height - 175, "This certificate is presented to")

        name_size = self._fit_font_size(pdf, recipient_name, max_width=page_width - 180)
        pdf.setFont("Helvetica-Bold", name_size)
        pdf.drawCentredString(page_width / 2, page_height - 235, recipient_name)

        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(page_width / 2, page_height - 285, "for successful participation in")
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(page_width / 2, page_height - 320, event_name)

        pdf.setFont("Helvetica", 11)
        pdf.drawString(margin + 28, margin + 34, f"Issued: {issue_date.isoformat()}")
        pdf.drawRightString(
            page_width - margin - 28,
            margin + 34,
            f"Certificate ID: {certificate_id}",
        )

        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    @staticmethod
    def _fit_font_size(pdf: canvas.Canvas, text: str, max_width: float) -> int:
        size = 30
        while size > 16 and pdf.stringWidth(text, "Helvetica-Bold", size) > max_width:
            size -= 1
        return size
