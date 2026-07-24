"""
PDF Report Generator
---------------------
Turns a quality-check summary into a polished, downloadable PDF report.
"""

from fpdf import FPDF, XPos, YPos
from datetime import datetime


def _safe_text(text):
    """Core PDF fonts (Helvetica) only support latin-1. Replace common
    unicode punctuation with ASCII equivalents so multi_cell doesn't choke."""
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2026": "...",
    }
    for uni, ascii_eq in replacements.items():
        text = text.replace(uni, ascii_eq)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class QualityReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Data Quality Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def generate_pdf_report(summary, suggestions, dataset_name="dataset.csv", output_path="quality_report.pdf"):
    pdf = QualityReportPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Dataset: {dataset_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Score summary box
    pdf.set_font("Helvetica", "B", 14)
    score = summary["overall_score"]
    label = summary["quality_label"]
    if score >= 90:
        pdf.set_text_color(39, 174, 96)
    elif score >= 75:
        pdf.set_text_color(243, 156, 18)
    else:
        pdf.set_text_color(231, 76, 60)
    pdf.cell(0, 10, f"Overall Quality Score: {score}/100  ({label})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Completeness Score: {summary['completeness_score']}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Table of checks
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(90, 8, "Check", border=1, fill=True)
    pdf.cell(40, 8, "Status", border=1, fill=True, align="C")
    pdf.cell(40, 8, "Issues Found", border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    report_df = summary["report"]
    for _, row in report_df.iterrows():
        status_text = {"✅": "OK", "⚠️": "WARN", "❌": "FAIL"}.get(row["Status"], row["Status"])
        pdf.cell(90, 8, _safe_text(str(row["Check"]))[:45], border=1)
        pdf.cell(40, 8, status_text, border=1, align="C")
        pdf.cell(40, 8, str(row["Issues Found"]), border=1, align="C")
        pdf.ln()

    pdf.ln(6)

    # Suggestions
    if suggestions:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Suggestions", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        for tip in suggestions:
            pdf.multi_cell(
                0, 6, _safe_text(f"- {tip}"),
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        pdf.ln(2)

    pdf.output(output_path)
    return output_path
