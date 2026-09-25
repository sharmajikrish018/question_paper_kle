"""
services/pdf_service.py
Centralized PDF generation for all pages using ReportLab.
Supports: Question Papers, Valuation Schemes, Validation Reports,
          Question Bank listings, Usage History, and Dashboard summaries.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Colour palette ─────────────────────────────────────────────────────────────
_NAVY     = (0.059, 0.090, 0.165)   # #0f172a
_BLUE     = (0.227, 0.408, 0.980)   # #3a68fa
_SLATE    = (0.302, 0.400, 0.510)   # #4d6682
_LIGHT    = (0.949, 0.957, 0.969)   # #f1f5f8
_RED      = (0.780, 0.118, 0.118)   # #c71e1e
_GREEN    = (0.024, 0.373, 0.275)   # #065f46
_AMBER    = (0.706, 0.353, 0.047)   # #b45909
_WHITE    = (1.0,   1.0,   1.0)
_BLACK    = (0.0,   0.0,   0.0)
_DARK_TXT = (0.094, 0.122, 0.173)   # #18213b


def _rl():
    """Lazy import of reportlab components."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak, KeepTogether,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        return {
            "A4": A4, "mm": mm, "StyleSheet": getSampleStyleSheet,
            "ParagraphStyle": ParagraphStyle, "colors": colors,
            "SimpleDocTemplate": SimpleDocTemplate, "Paragraph": Paragraph,
            "Spacer": Spacer, "Table": Table, "TableStyle": TableStyle,
            "HRFlowable": HRFlowable, "PageBreak": PageBreak,
            "KeepTogether": KeepTogether,
            "TA_CENTER": TA_CENTER, "TA_LEFT": TA_LEFT,
            "TA_RIGHT": TA_RIGHT, "TA_JUSTIFY": TA_JUSTIFY,
        }
    except ImportError as e:
        raise RuntimeError("reportlab is required for PDF export. Run: pip install reportlab") from e


def _color(rgb: tuple) -> Any:
    rl = _rl()
    return rl["colors"].Color(*rgb)


# ── Style factory ──────────────────────────────────────────────────────────────

def _make_styles():
    rl = _rl()
    PS = rl["ParagraphStyle"]
    base = rl["StyleSheet"]()

    styles = {
        "doc_title": PS("DocTitle",
            fontSize=18, fontName="Helvetica-Bold",
            textColor=_color(_WHITE), leading=22,
            alignment=rl["TA_CENTER"], spaceAfter=2),
        "doc_sub": PS("DocSub",
            fontSize=10, fontName="Helvetica",
            textColor=_color(_LIGHT), leading=13,
            alignment=rl["TA_CENTER"], spaceAfter=2),
        "section": PS("Section",
            fontSize=12, fontName="Helvetica-Bold",
            textColor=_color(_NAVY), leading=15,
            spaceBefore=10, spaceAfter=4),
        "q_number": PS("QNumber",
            fontSize=11, fontName="Helvetica-Bold",
            textColor=_color(_BLUE), leading=14,
            spaceBefore=8, spaceAfter=2),
        "q_text": PS("QText",
            fontSize=10, fontName="Helvetica",
            textColor=_color(_DARK_TXT), leading=14,
            leftIndent=18, spaceAfter=3,
            alignment=rl["TA_JUSTIFY"]),
        "marks": PS("Marks",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=_color(_SLATE), leading=12,
            leftIndent=18, spaceAfter=6),
        "watermark": PS("Watermark",
            fontSize=13, fontName="Helvetica-Bold",
            textColor=_color(_RED), leading=16,
            alignment=rl["TA_CENTER"], spaceBefore=0, spaceAfter=6),
        "body": PS("Body",
            fontSize=9.5, fontName="Helvetica",
            textColor=_color(_DARK_TXT), leading=13,
            spaceAfter=4),
        "caption": PS("Caption",
            fontSize=8, fontName="Helvetica-Oblique",
            textColor=_color(_SLATE), leading=11,
            spaceAfter=4),
        "footer": PS("Footer",
            fontSize=7.5, fontName="Helvetica",
            textColor=_color(_SLATE), leading=10,
            alignment=rl["TA_CENTER"]),
    }
    return styles


# ── Header builder ─────────────────────────────────────────────────────────────

def _header_table(title: str, subtitle: str, meta: str, is_draft: bool = False):
    """Returns a styled banner Table for the top of every PDF."""
    rl = _rl()
    Paragraph = rl["Paragraph"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    colors = rl["colors"]

    s = _make_styles()
    bg = _color(_RED if is_draft else _NAVY)

    content = [
        Paragraph(("⚠  DRAFT — NOT FOR DISTRIBUTION  ⚠<br/>" if is_draft else "") + title, s["doc_title"]),
        Paragraph(subtitle, s["doc_sub"]),
    ]
    if meta:
        content.append(Paragraph(meta, s["doc_sub"]))

    tbl = Table([[content]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [8]),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
    ]))
    return tbl


# ══════════════════════════════════════════════════════════════════════════════
# 1. QUESTION PAPER PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_paper_pdf(
    paper_set,          # PaperSet domain object
    academic_year: str = "",
    course_name: str = "Generative AI",
    department: str = "Department of Computer Science",
    is_draft: bool = False,
) -> bytes:
    """Generate a formatted question paper PDF. Returns raw bytes."""
    rl = _rl()
    buf = io.BytesIO()

    doc = rl["SimpleDocTemplate"](
        buf, pagesize=rl["A4"],
        leftMargin=20*rl["mm"], rightMargin=20*rl["mm"],
        topMargin=18*rl["mm"], bottomMargin=18*rl["mm"],
    )

    exam_type = paper_set.exam_type if isinstance(paper_set.exam_type, str) else paper_set.exam_type.value
    is_minor = exam_type == "MINOR"
    duration = "75 minutes" if is_minor else "180 minutes"
    max_marks = "40" if is_minor else "100"
    exam_label = "Minor / Internal Examination" if is_minor else "End-Semester Examination"

    s = _make_styles()
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    HRFlowable = rl["HRFlowable"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    KeepTogether = rl["KeepTogether"]
    mm = rl["mm"]

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(_header_table(
        title=f"{course_name}",
        subtitle=f"{exam_label}  |  Set: {paper_set.set_id}",
        meta=f"{department}  |  Duration: {duration}  |  Max Marks: {max_marks}"
             + (f"  |  Academic Year: {academic_year}" if academic_year else ""),
        is_draft=is_draft,
    ))
    story.append(Spacer(1, 8*mm))

    # ── Instructions ──────────────────────────────────────────────────────────
    if is_minor:
        instr = "Answer any TWO complete questions. Each complete question carries 20 marks."
    else:
        instr = (
            "Unit 1 & 2: Answer any TWO complete questions from each unit. "
            "Unit 3: Answer any ONE complete question. Each complete question carries 20 marks."
        )
    story.append(Paragraph(f"<b>General Instructions:</b> {instr}", s["body"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_color(_BLUE), spaceAfter=6))

    # ── Questions ─────────────────────────────────────────────────────────────
    questions = sorted(paper_set.questions, key=lambda q: (q.main_question_number, q.part))
    current_main = None

    for pq in questions:
        block = []
        if pq.main_question_number != current_main:
            current_main = pq.main_question_number
            # Unit label for end-sem
            if not is_minor:
                unit_lbl = f"  (Unit {pq.unit_number})"
            else:
                unit_lbl = ""
            block.append(Paragraph(f"Q{pq.main_question_number}.{unit_lbl}", s["q_number"]))

        # Part line
        qt = pq.question_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        block.append(Paragraph(
            f"<b>({pq.part})</b>  {qt}",
            s["q_text"]
        ))
        block.append(Paragraph(f"[{pq.marks} Marks]", s["marks"]))
        story.append(KeepTogether(block))

    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_color(_SLATE)))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"CONFIDENTIAL — Faculty use only",
        s["footer"]
    ))

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 2. VALUATION SCHEME PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_scheme_pdf(paper_set, is_draft: bool = False) -> bytes:
    """Generate Scheme of Valuation PDF. Returns raw bytes."""
    rl = _rl()
    buf = io.BytesIO()
    doc = rl["SimpleDocTemplate"](
        buf, pagesize=rl["A4"],
        leftMargin=20*rl["mm"], rightMargin=20*rl["mm"],
        topMargin=18*rl["mm"], bottomMargin=18*rl["mm"],
    )

    exam_type = paper_set.exam_type if isinstance(paper_set.exam_type, str) else paper_set.exam_type.value
    s = _make_styles()
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    HRFlowable = rl["HRFlowable"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    KeepTogether = rl["KeepTogether"]
    mm = rl["mm"]
    colors = rl["colors"]

    story = []
    story.append(_header_table(
        title="Scheme of Valuation",
        subtitle=f"Set: {paper_set.set_id}  |  Generative AI",
        meta="STRICTLY CONFIDENTIAL — For examiner use only",
        is_draft=is_draft,
    ))
    story.append(Spacer(1, 8*mm))

    questions = sorted(paper_set.questions, key=lambda q: (q.main_question_number, q.part))

    for pq in questions:
        block = []
        qt = pq.question_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        block.append(Paragraph(
            f"<b>Q{pq.main_question_number}({pq.part})</b>  {qt[:120]}{'…' if len(qt) > 120 else ''}",
            s["q_number"]
        ))
        block.append(Paragraph(
            f"Bloom: <b>{pq.bloom_level}</b>  |  Source: {pq.source}  |  Marks: <b>{pq.marks}</b>",
            s["caption"]
        ))

        if pq.valuation_scheme:
            vs = pq.valuation_scheme
            # Expected answer
            ans = (vs.expected_answer or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            block.append(Paragraph("<b>Expected Answer:</b>", s["body"]))
            block.append(Paragraph(ans, s["q_text"]))

            # Valuation table
            if vs.valuation_points:
                data = [["Criterion", "Marks"]]
                for vp in vs.valuation_points:
                    crit = (vp.criterion or "").replace("&", "&amp;")
                    data.append([crit, str(vp.marks)])
                data.append(["<b>Total</b>", f"<b>{sum(vp.marks for vp in vs.valuation_points)}</b>"])

                tbl = Table(data, colWidths=[380, 60])
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), _color(_NAVY)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _color(_WHITE)),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ALIGN", (1, 0), (1, -1), "CENTER"),
                    ("BACKGROUND", (0, -1), (-1, -1), _color(_LIGHT)),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, _color(_SLATE)),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [_color(_WHITE), _color(_LIGHT)]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]))
                block.append(Spacer(1, 3*mm))
                block.append(tbl)
        else:
            block.append(Paragraph("[Valuation scheme not yet generated]", s["caption"]))

        block.append(HRFlowable(width="100%", thickness=0.4, color=_color(_SLATE), spaceBefore=6, spaceAfter=2))
        story.append(KeepTogether(block))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  CONFIDENTIAL",
        s["footer"]
    ))
    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 3. VALIDATION REPORT PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_validation_report_pdf(
    set_id: str,
    exam_type: str,
    validation_status: str,
    findings: list[dict],
) -> bytes:
    """Generate a formatted Validation Report PDF. Returns raw bytes."""
    rl = _rl()
    buf = io.BytesIO()
    doc = rl["SimpleDocTemplate"](
        buf, pagesize=rl["A4"],
        leftMargin=20*rl["mm"], rightMargin=20*rl["mm"],
        topMargin=18*rl["mm"], bottomMargin=18*rl["mm"],
    )

    s = _make_styles()
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    HRFlowable = rl["HRFlowable"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    mm = rl["mm"]

    status_color = {
        "PASS": _GREEN, "PASS_WITH_WARNINGS": _AMBER, "FAIL": _RED
    }.get(validation_status, _SLATE)

    story = []
    story.append(_header_table(
        title="Validation Report",
        subtitle=f"Set: {set_id}  |  Exam: {exam_type}",
        meta=f"Status: {validation_status}  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ))
    story.append(Spacer(1, 6*mm))

    # Status badge
    errors = [f for f in findings if f.get("severity") == "ERROR"]
    warnings = [f for f in findings if f.get("severity") == "WARNING"]

    summary_data = [
        ["Overall Status", validation_status],
        ["Errors", str(len(errors))],
        ["Warnings", str(len(warnings))],
        ["Total Findings", str(len(findings))],
    ]
    summary_tbl = Table(summary_data, colWidths=[160, 280])
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), _color(_LIGHT)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, _color(_SLATE)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 6*mm))

    if not findings:
        story.append(Paragraph("✅  All validation rules passed. No issues found.", s["body"]))
    else:
        story.append(Paragraph("Findings Detail", s["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_color(_BLUE), spaceAfter=4))

        for i, f in enumerate(findings, 1):
            sev = f.get("severity", "INFO")
            icon = "🔴" if sev == "ERROR" else "🟡"
            rule_id = f.get("rule_id", "—")
            message = (f.get("message", "") or "").replace("&", "&amp;").replace("<", "&lt;")
            expected = f.get("expected")
            actual = f.get("actual")
            action = (f.get("suggested_action", "") or "").replace("&", "&amp;").replace("<", "&lt;")
            affected = f.get("affected_questions", [])

            story.append(Paragraph(
                f"<b>[{i}] {icon} [{rule_id}]</b>  {message}",
                s["body"]
            ))
            if expected is not None:
                story.append(Paragraph(f"Expected: <b>{expected}</b>", s["caption"]))
            if actual is not None:
                story.append(Paragraph(f"Actual: <b>{actual}</b>", s["caption"]))
            if affected:
                story.append(Paragraph(f"Affected slots: {', '.join(str(a) for a in affected)}", s["caption"]))
            if action:
                story.append(Paragraph(f"Action: {action}", s["caption"]))
            story.append(Spacer(1, 2*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=_color(_SLATE), spaceBefore=8))
    story.append(Paragraph("CONFIDENTIAL — Faculty and examiner use only", s["footer"]))
    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 4. QUESTION BANK PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_question_bank_pdf(questions: list[dict]) -> bytes:
    """Generate a formatted Question Bank listing PDF. Returns raw bytes."""
    rl = _rl()
    buf = io.BytesIO()
    doc = rl["SimpleDocTemplate"](
        buf, pagesize=rl["A4"],
        leftMargin=15*rl["mm"], rightMargin=15*rl["mm"],
        topMargin=18*rl["mm"], bottomMargin=15*rl["mm"],
    )

    s = _make_styles()
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    HRFlowable = rl["HRFlowable"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    mm = rl["mm"]

    story = []
    story.append(_header_table(
        title="Approved Question Bank",
        subtitle="Generative AI — Full Listing",
        meta=f"{len(questions)} questions  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ))
    story.append(Spacer(1, 6*mm))

    # Group by chapter
    by_chapter: dict[int, list[dict]] = {}
    for q in questions:
        ch = q.get("Chapter", 0)
        by_chapter.setdefault(ch, []).append(q)

    for ch in sorted(by_chapter):
        qs = by_chapter[ch]
        ch_name = qs[0].get("Ch Name", f"Chapter {ch}")
        story.append(Paragraph(f"Chapter {ch}: {ch_name}", s["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=_color(_BLUE), spaceAfter=3))

        for q in qs:
            bloom = q.get("Bloom", "")
            bloom_color = _GREEN if bloom == "L2" else _AMBER
            text = (q.get("Text", "") or "").replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(
                f"<font color='#{_hex(bloom_color)}'><b>[{bloom}]</b></font>  {text}",
                s["body"]
            ))
            story.append(Paragraph(
                f"ID: {q.get('ID','')}  |  Unit: {q.get('Unit','')}  |  "
                f"Marks: {q.get('Marks','')}  |  Status: {q.get('Status','')}  |  Used: {q.get('Used',0)}×",
                s["caption"]
            ))

        story.append(Spacer(1, 4*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=_color(_SLATE)))
    story.append(Paragraph("CONFIDENTIAL — Approved question bank listing", s["footer"]))
    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 5. USAGE HISTORY PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_usage_history_pdf(rows: list[dict]) -> bytes:
    """Generate Usage History PDF as a table. Returns raw bytes."""
    rl = _rl()
    buf = io.BytesIO()
    doc = rl["SimpleDocTemplate"](
        buf, pagesize=rl["A4"],
        leftMargin=15*rl["mm"], rightMargin=15*rl["mm"],
        topMargin=18*rl["mm"], bottomMargin=15*rl["mm"],
    )

    s = _make_styles()
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    mm = rl["mm"]

    story = []
    story.append(_header_table(
        title="Question Usage History",
        subtitle="Generative AI — Question Paper Setting Agent",
        meta=f"{len(rows)} records  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ))
    story.append(Spacer(1, 6*mm))

    # Table
    headers = ["Question ID", "Source", "Paper Set", "Exam Type", "Year", "Used At"]
    data = [headers]
    for r in rows:
        data.append([
            r.get("Question ID", ""),
            r.get("Source", ""),
            r.get("Paper Set", ""),
            r.get("Exam Type", ""),
            r.get("Academic Year", ""),
            r.get("Used At", ""),
        ])

    col_widths = [120, 80, 80, 60, 50, 80]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _color(_NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), _color(_WHITE)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_color(_WHITE), _color(_LIGHT)]),
        ("GRID", (0, 0), (-1, -1), 0.4, _color(_SLATE)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("WORDWRAP", (0, 0), (-1, -1), True),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))
    from reportlab.lib.styles import ParagraphStyle as _PS
    story.append(Paragraph("CONFIDENTIAL", s["footer"]))
    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 6. DASHBOARD SUMMARY PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_dashboard_pdf(
    total_questions: int,
    l2_count: int,
    l3_count: int,
    total_sets: int,
    pending_sets: int,
    approved_sets: int,
    exported_sets: int,
    completeness_rows: list[dict],
) -> bytes:
    """Generate a Dashboard Summary PDF. Returns raw bytes."""
    rl = _rl()
    buf = io.BytesIO()
    doc = rl["SimpleDocTemplate"](
        buf, pagesize=rl["A4"],
        leftMargin=20*rl["mm"], rightMargin=20*rl["mm"],
        topMargin=18*rl["mm"], bottomMargin=15*rl["mm"],
    )

    s = _make_styles()
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    HRFlowable = rl["HRFlowable"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    mm = rl["mm"]

    story = []
    story.append(_header_table(
        title="Question Paper Setting Agent",
        subtitle="Dashboard Summary — Generative AI Course",
        meta=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ))
    story.append(Spacer(1, 6*mm))

    # Question bank stats
    story.append(Paragraph("Question Bank", s["section"]))
    qb_data = [
        ["Total Questions", str(total_questions), "L2 Questions", str(l2_count)],
        ["L3 Questions", str(l3_count), "Completeness", f"{min(total_questions, 140)}/140"],
    ]
    qb_tbl = Table(qb_data, colWidths=[110, 110, 110, 110])
    qb_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _color(_LIGHT)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, _color(_SLATE)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(qb_tbl)
    story.append(Spacer(1, 5*mm))

    # Paper generation stats
    story.append(Paragraph("Paper Generation", s["section"]))
    pg_data = [
        ["Total Sets", str(total_sets), "Awaiting Review", str(pending_sets)],
        ["Approved", str(approved_sets), "Exported", str(exported_sets)],
    ]
    pg_tbl = Table(pg_data, colWidths=[110, 110, 110, 110])
    pg_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _color(_LIGHT)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, _color(_SLATE)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(pg_tbl)
    story.append(Spacer(1, 5*mm))

    # Chapter completeness matrix
    if completeness_rows:
        story.append(Paragraph("Chapter Completeness Matrix", s["section"]))
        tbl_data = [["Unit", "Chapter", "L2", "L3", "Total", "Status"]]
        for r in completeness_rows:
            tbl_data.append([
                r.get("Unit", ""), r.get("Chapter", ""),
                str(r.get("L2", 0)), str(r.get("L3", 0)),
                str(r.get("Total", 0)), r.get("Ready", ""),
            ])
        matrix_tbl = Table(tbl_data, colWidths=[60, 60, 50, 50, 50, 170])
        matrix_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _color(_NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), _color(_WHITE)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_color(_WHITE), _color(_LIGHT)]),
            ("GRID", (0, 0), (-1, -1), 0.4, _color(_SLATE)),
            ("ALIGN", (2, 0), (4, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(matrix_tbl)

    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_color(_SLATE)))
    story.append(Paragraph("CONFIDENTIAL — Internal faculty document", s["footer"]))
    doc.build(story)
    return buf.getvalue()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hex(rgb: tuple) -> str:
    """Convert (r,g,b) floats 0-1 to hex string without #."""
    return "{:02x}{:02x}{:02x}".format(
        int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)
    )
