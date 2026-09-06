"""
PDF Generator for Flawless Take Continuity Logs.
Uses ReportLab with UTF-8 / Cyrillic TrueType font support.
"""
from __future__ import annotations

import io
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import storage

# ---------------------------------------------------------------------------
# Font setup with UTF-8 / Cyrillic support
# ---------------------------------------------------------------------------
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

def _init_fonts() -> tuple[str, str]:
    """Register Arial or Segoe UI for Unicode/Cyrillic support if available."""
    candidates = [
        ("AppArial", "C:/Windows/Fonts/arial.ttf", "AppArialBold", "C:/Windows/Fonts/arialbd.ttf"),
        ("AppSegoe", "C:/Windows/Fonts/segoeui.ttf", "AppSegoeBold", "C:/Windows/Fonts/segoeuib.ttf"),
        ("AppCalibri", "C:/Windows/Fonts/calibri.ttf", "AppCalibriBold", "C:/Windows/Fonts/calibrib.ttf"),
    ]
    for reg_name, reg_path, bold_name, bold_path in candidates:
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            try:
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                return reg_name, bold_name
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"

FONT_REGULAR, FONT_BOLD = _init_fonts()


def _format_inline_markdown(text: str) -> str:
    """Safely convert basic markdown bold/italic into ReportLab XML tags."""
    # Escape XML entities first
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert bold and italic to ReportLab tags
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
    return t


# ---------------------------------------------------------------------------
# PDF Generation Function
# ---------------------------------------------------------------------------
def generate_continuity_pdf(record: dict[str, Any]) -> bytes:

    """
    Build a PDF Continuity Log from a database record and return raw PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles using our registered UTF-8 fonts
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A1D20"),
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#6E56CF"),
        alignment=0,
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
    )

    meta_val_style = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#111827"),
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#6E56CF"),
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )

    bullet_style = ParagraphStyle(
        "BulletCustom",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )

    elements = []

    # --- Header Banner ---
    kind_label = "TAKE COMPARISON REPORT" if record.get("kind") == "comparison" else "CONTINUITY CHECK REPORT"
    date_str = datetime.fromtimestamp(record.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")

    header_table = Table(
        [
            [
                Paragraph("FLAWLESS TAKE", title_style),
                Paragraph(f"<b>DATE:</b> {date_str}<br/><b>STATUS:</b> OFFICIAL LOG", meta_label_style),
            ],
            [
                Paragraph(f"SCRIPT SUPERVISOR CONTINUITY LOG &bull; {kind_label}", subtitle_style),
                Paragraph(f"<b>RECORD ID:</b> #{record.get('id')}", meta_label_style),
            ],
        ],
        colWidths=[360, 160],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    elements.append(header_table)
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#6E56CF"), spaceAfter=10))

    # --- Metadata Card ---
    scene = record.get("scene", "N/A")
    character = record.get("character", "N/A")
    risk = (record.get("risk_level") or "UNKNOWN").upper()
    match_score = (record.get("match_score") or "").upper()
    grounded = "Yes (PDF Script Attached)" if record.get("script_grounded") else "No"

    if record.get("kind") == "comparison":
        takes_text = f"Ref Take: <b>{record.get('take_ref', '?')}</b> &nbsp;|&nbsp; Current Take: <b>{record.get('take_current', '?')}</b>"
    else:
        takes_text = f"Take: <b>{record.get('take', '?')}</b>"

    risk_colors = {
        "HIGH": "#E5484D",
        "MEDIUM": "#F76808",
        "LOW": "#30A46C",
    }
    risk_hex = risk_colors.get(risk, "#6B7280")
    risk_html = f'<font color="{risk_hex}"><b>{risk}</b></font>'
    match_html = f" &bull; Match: <b>{match_score}</b>" if match_score else ""

    meta_data = [
        [
            Paragraph("<b>Scene:</b>", meta_label_style),
            Paragraph(scene, meta_val_style),
            Paragraph("<b>Continuity Risk:</b>", meta_label_style),
            Paragraph(f"{risk_html}{match_html}", meta_val_style),
        ],
        [
            Paragraph("<b>Character:</b>", meta_label_style),
            Paragraph(character, meta_val_style),
            Paragraph("<b>Script Grounding:</b>", meta_label_style),
            Paragraph(grounded, meta_val_style),
        ],
        [
            Paragraph("<b>Takes:</b>", meta_label_style),
            Paragraph(takes_text, meta_val_style),
            Paragraph("<b>Engine:</b>", meta_label_style),
            Paragraph("Gemini 3.8 Flash + Confluent", meta_val_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[70, 190, 100, 160])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    # --- Previews / Photos Section ---
    ref_fn = record.get("preview_ref")
    cur_fn = record.get("preview_cur")

    def _make_image_flowable(filename: str | None, max_w: float, max_h: float) -> RLImage | None:
        if not filename:
            return None
        img_path = storage.UPLOADS_DIR / filename
        if not img_path.exists():
            return None
        try:
            img = RLImage(str(img_path))
            # compute proportional scale
            orig_w, orig_h = img.drawWidth, img.drawHeight
            ratio = min(max_w / orig_w, max_h / orig_h)
            img.drawWidth = orig_w * ratio
            img.drawHeight = orig_h * ratio
            return img
        except Exception:
            return None

    if record.get("kind") == "comparison":
        img_ref = _make_image_flowable(ref_fn, 240, 160)
        img_cur = _make_image_flowable(cur_fn, 240, 160)

        if img_ref or img_cur:
            ref_cell = [img_ref, Paragraph(f"<b>REFERENCE TAKE #{record.get('take_ref', '')}</b>", subtitle_style)] if img_ref else [Paragraph("No reference image", body_style)]
            cur_cell = [img_cur, Paragraph(f"<b>CURRENT TAKE #{record.get('take_current', '')}</b>", subtitle_style)] if img_cur else [Paragraph("No current image", body_style)]

            img_table = Table([[ref_cell, cur_cell]], colWidths=[260, 260])
            img_table.setStyle(
                TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            elements.append(img_table)
            elements.append(Spacer(1, 10))
    else:
        img_single = _make_image_flowable(ref_fn, 320, 180)
        if img_single:
            img_table = Table([[[img_single, Paragraph(f"<b>TAKE #{record.get('take', '')} REFERENCE PHOTO</b>", subtitle_style)]]], colWidths=[520])
            img_table.setStyle(
                TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            elements.append(img_table)
            elements.append(Spacer(1, 10))

    # --- Report Content ---
    elements.append(Paragraph("CONTINUITY EVALUATION &amp; DISCREPANCY ANALYSIS", heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
    report_text = record.get("report", "")
    lines = report_text.split("\n")

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Markdown headers (# or ## or 1. **Section**)
        if re.match(r"^#{1,3}\s", line):
            header_clean = re.sub(r"^#{1,3}\s*", "", line)
            elements.append(Paragraph(_format_inline_markdown(header_clean), heading_style))
        elif re.match(r"^\d+\.\s+\*\*(.+?)\*\*", line):
            # Format: 1. **Makeup & Hair**
            elements.append(Paragraph(_format_inline_markdown(line), heading_style))
        elif line.startswith(("- ", "* ")):
            bullet_content = line[2:].strip()
            elements.append(Paragraph(f"&bull; {_format_inline_markdown(bullet_content)}", bullet_style))
        else:
            elements.append(Paragraph(_format_inline_markdown(line), body_style))


    elements.append(Spacer(1, 16))

    # --- Sign-off Footer ---
    sign_table = Table(
        [
            [
                Paragraph("<b>Continuity Supervisor:</b> ___________________________", meta_label_style),
                Paragraph("<b>Director / DP Approval:</b> ___________________________", meta_label_style),
            ]
        ],
        colWidths=[260, 260],
    )
    sign_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(sign_table)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Generated by Flawless Take &bull; Agentic Cinema Workflow &bull; IBM Watsonx / Bob Partner Track", subtitle_style))

    # Build PDF into memory
    doc.build(elements)
    return buffer.getvalue()
