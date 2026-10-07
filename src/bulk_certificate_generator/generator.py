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

        self._draw_fitted_centered_text(
            pdf,
            title,
            center_x=page_width / 2,
            center_y=page_height - 120,
            font_name="Helvetica-Bold",
            max_font_size=30,
            min_font_size=10,
            max_width=page_width - 150,
            max_lines=3,
        )
        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(page_width / 2, page_height - 175, "This certificate is presented to")

        self._draw_fitted_centered_text(
            pdf,
            recipient_name,
            center_x=page_width / 2,
            center_y=page_height - 235,
            font_name="Helvetica-Bold",
            max_font_size=30,
            min_font_size=10,
            max_width=page_width - 180,
            max_lines=3,
        )

        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(page_width / 2, page_height - 285, "for successful participation in")
        self._draw_fitted_centered_text(
            pdf,
            event_name,
            center_x=page_width / 2,
            center_y=page_height - 320,
            font_name="Helvetica-Bold",
            max_font_size=18,
            min_font_size=10,
            max_width=page_width - 180,
            max_lines=3,
        )

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

    @classmethod
    def _draw_fitted_centered_text(
        cls,
        pdf: canvas.Canvas,
        text: str,
        *,
        center_x: float,
        center_y: float,
        font_name: str,
        max_font_size: int,
        min_font_size: int,
        max_width: float,
        max_lines: int,
    ) -> None:
        font_size, lines = cls._fit_lines(
            pdf,
            text,
            font_name=font_name,
            max_font_size=max_font_size,
            min_font_size=min_font_size,
            max_width=max_width,
            max_lines=max_lines,
        )
        leading = font_size * 1.2
        first_y = center_y + leading * (len(lines) - 1) / 2

        pdf.setFont(font_name, font_size)
        for index, line in enumerate(lines):
            pdf.drawCentredString(center_x, first_y - index * leading, line)

    @classmethod
    def _fit_lines(
        cls,
        pdf: canvas.Canvas,
        text: str,
        *,
        font_name: str,
        max_font_size: int,
        min_font_size: int,
        max_width: float,
        max_lines: int,
    ) -> tuple[int, list[str]]:
        for font_size in range(max_font_size, min_font_size - 1, -1):
            lines = cls._wrap_text(pdf, text, font_name, font_size, max_width)
            if len(lines) <= max_lines:
                return font_size, lines
        raise ValueError("Certificate text does not fit the predefined template")

    @staticmethod
    def _wrap_text(
        pdf: canvas.Canvas,
        text: str,
        font_name: str,
        font_size: int,
        max_width: float,
    ) -> list[str]:
        remaining = text
        lines: list[str] = []

        while remaining:
            if pdf.stringWidth(remaining, font_name, font_size) <= max_width:
                lines.append(remaining)
                break

            cut = 1
            for index in range(2, len(remaining) + 1):
                if pdf.stringWidth(remaining[:index], font_name, font_size) > max_width:
                    cut = index - 1
                    break
            else:
                cut = len(remaining)

            space = remaining.rfind(" ", 0, cut + 1)
            if space > 0:
                cut = space

            lines.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()

        return lines
