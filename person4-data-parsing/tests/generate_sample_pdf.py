"""Regenerates tests/sample_offer_letter.pdf.

The committed PDF is what test_parser_pdf.py actually runs against — this
script is only needed if you want to regenerate or modify that fixture.
Requires `reportlab` (a test-fixture-generation dependency only, not a
runtime dependency of the parser — see requirements.txt).

Run from the person4-data-parsing/ directory:
    python tests/generate_sample_pdf.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUTPUT_PATH = Path(__file__).parent / "sample_offer_letter.pdf"


def build() -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUTPUT_PATH), pagesize=A4)

    story = [
        Paragraph("Company Name: Delta Analytics Pvt Ltd", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Dear Meera Iyer,", styles["Normal"]),
        Paragraph(
            "We are thrilled to extend an offer of employment to you at Delta Analytics Pvt Ltd "
            "for the position of Machine Learning Engineer.", styles["Normal"]),
        Paragraph(
            "Your Total Compensation (CTC) for the year will be Rs. 22,00,000.", styles["Normal"]),
        Spacer(1, 16),
        Paragraph("Annexure A: Compensation Breakup", styles["Heading3"]),
    ]

    table_data = [
        ["Component", "Monthly (Rs.)", "Annual (Rs.)"],
        ["Basic Pay", "80,000", "9,60,000"],
        ["House Rent Allowance", "40,000", "4,80,000"],
        ["Special Allowance", "30,000", "3,60,000"],
        ["Employer PF", "9,600", "1,15,200"],
        ["Gratuity", "3,846", "46,154"],
    ]
    table = Table(table_data, colWidths=[180, 120, 120])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "You will also be eligible for a Joining Bonus of Rs. 1,50,000, subject to a "
        "Clawback Period of 6 months.", styles["Normal"]))

    doc.build(story)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
