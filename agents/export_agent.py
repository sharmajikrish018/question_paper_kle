"""
agents/export_agent.py
Exports approved question papers and schemes to DOCX and PDF.
Updates usage history on export.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import get_settings
from models.enums import ExamType, PaperSetStatus
from models.paper import PaperSet
from models.validation import ValidationReport
from repositories.paper_repo import PaperRepository
from repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)

DRAFT_WATERMARK = "DRAFT — NOT APPROVED — FOR REVIEW ONLY"


def build_meaningful_filename(
    course_name: str,
    exam_type: str,
    set_id: str,
    extension: str = "docx",
    is_draft: bool = False,
) -> str:
    """
    Generate clean, standardized filename for paper export:
    {Sanitized_Subject}_{ExamType}_{Date}_Set-{Label}.{ext}
    """
    import re
    sanitized_subject = re.sub(r'[^a-zA-Z0-9_\-]', '', course_name.replace(' ', '_'))
    sanitized_subject = re.sub(r'_+', '_', sanitized_subject).strip('_')
    if not sanitized_subject:
        sanitized_subject = "QP"

    clean_exam_type = re.sub(r'[^a-zA-Z0-9]', '', str(exam_type)).upper() or "EXAM"

    parts = set_id.split('-')
    if len(parts) >= 2 and parts[-2].upper().startswith("SET"):
        set_label = f"Set-{parts[-1].upper()}"
    elif "SET" in set_id.upper():
        match = re.search(r'SET[-_]?([A-Z0-9]+)', set_id.upper())
        set_label = f"Set-{match.group(1)}" if match else f"Set-{set_id}"
    else:
        set_label = f"Set-{set_id}"

    date_str = datetime.utcnow().strftime('%Y%m%d')
    prefix = "DRAFT_" if is_draft else ""
    ext = extension.lstrip('.')

    return f"{prefix}{sanitized_subject}_{clean_exam_type}_{date_str}_{set_label}.{ext}"


def _render_tabular_docx(doc, paper_set: PaperSet, is_draft: bool = False, course_name: str = "Agentic AI") -> None:
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    if is_draft:
        draft_p = doc.add_paragraph("DRAFT — NOT APPROVED — FOR REVIEW ONLY")
        draft_p.runs[0].bold = True
        draft_p.runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
        draft_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    exam_type_val = paper_set.exam_type if isinstance(paper_set.exam_type, str) else paper_set.exam_type.value
    is_minor = (exam_type_val == "MINOR")

    # Derive ISA sub-type label from set_id
    set_id_str = getattr(paper_set, "set_id", "") or ""
    isa_label = "ISA-I"
    if "ISA-II" in set_id_str.upper() or "ISA2" in set_id_str.upper():
        isa_label = "ISA-II"

    if is_minor:
        header_title = getattr(paper_set, "exam_title", None) or \
            f"Question Paper for Minor Examination ({isa_label})"
        duration_str = getattr(paper_set, "duration", None) or "60 mins"
        max_marks_str = str(getattr(paper_set, "max_marks", None) or "30")
        note_str = getattr(paper_set, "instructions", None) or "Note: Answer any two full questions. Each full question carries equal marks."
    else:
        header_title = getattr(paper_set, "exam_title", None) or \
            "Question Paper for End Semester Assessment (ESA)"
        duration_str = getattr(paper_set, "duration", None) or "180 mins"
        max_marks_str = str(getattr(paper_set, "max_marks", None) or "100")
        note_str = getattr(paper_set, "instructions", None) or "Note: Answer any two full questions from Unit 1 & 2, and one from Unit 3. Each full question carries equal marks."

    if not (note_str.startswith("Note:") or note_str.startswith("Note :")):
        note_str = f"Note: {note_str}"

    c_code_str = getattr(paper_set, "course_code", None) or "26ECAC401"
    c_title_str = getattr(paper_set, "course_title", None) or course_name or "Agentic AI"

    # Header Table: 4 rows, 2 cols
    hdr_table = doc.add_table(rows=4, cols=2)
    hdr_table.style = 'Table Grid'
    hdr_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Row 0: Title (merged)
    hdr_table.cell(0, 0).merge(hdr_table.cell(0, 1))
    p0 = hdr_table.cell(0, 0).paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r0 = p0.add_run(header_title)
    r0.bold = True

    # Row 1: Course Code / Title
    p1_0 = hdr_table.cell(1, 0).paragraphs[0]
    r1_0_b = p1_0.add_run("Course Code: ")
    r1_0_b.bold = True
    p1_0.add_run(c_code_str)

    p1_1 = hdr_table.cell(1, 1).paragraphs[0]
    r1_1_b = p1_1.add_run("Course Title: ")
    r1_1_b.bold = True
    p1_1.add_run(c_title_str)

    # Row 2: Duration / Max Marks
    p2_0 = hdr_table.cell(2, 0).paragraphs[0]
    r2_0_b = p2_0.add_run("Duration: ")
    r2_0_b.bold = True
    p2_0.add_run(duration_str)

    p2_1 = hdr_table.cell(2, 1).paragraphs[0]
    r2_1_b = p2_1.add_run("Max. Marks: ")
    r2_1_b.bold = True
    p2_1.add_run(max_marks_str)

    # Row 3: Note (merged)
    hdr_table.cell(3, 0).merge(hdr_table.cell(3, 1))
    p3 = hdr_table.cell(3, 0).paragraphs[0]
    r3 = p3.add_run(note_str)
    r3.italic = True

    doc.add_paragraph()  # Spacing

    # Question Table: 7 columns
    q_table = doc.add_table(rows=1, cols=7)
    q_table.style = 'Table Grid'
    q_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Sl.No.", "Questions", "Marks", "CO", "BL", "PO", "PI Code"]
    col_widths = [Inches(0.6), Inches(3.8), Inches(0.5), Inches(0.5), Inches(0.5), Inches(0.5), Inches(0.6)]

    hdr_cells = q_table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].width = col_widths[i]
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True

    from services.pdf_service import _get_sl_no, _get_q_text, _get_marks, _get_co, _get_bl, _get_po, _get_pi_code

    questions = sorted(paper_set.questions, key=lambda q: (getattr(q, "main_question_number", 1), getattr(q, "part", "a")))

    for pq in questions:
        row_cells = q_table.add_row().cells
        sl_no = _get_sl_no(pq)
        qt = _get_q_text(pq)
        marks = _get_marks(pq)
        co = _get_co(pq)
        bl = _get_bl(pq)
        po = _get_po(pq)
        pi_code = _get_pi_code(pq)

        vals = [sl_no, qt, marks, co, bl, po, pi_code]
        for i, val in enumerate(vals):
            row_cells[i].width = col_widths[i]
            p = row_cells[i].paragraphs[0]
            if i == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(val)


class ExportError(Exception):
    pass


class ExportAgent:
    """
    Agent node 9.12: Export and Logging Agent.
    Only permits final export when paper set status is APPROVED.
    Draft preview downloads are allowed but include a watermark.
    """

    def __init__(self):
        self._settings = get_settings()
        self._paper_repo = PaperRepository()
        self._audit_repo = AuditRepository()

    def export_paper(
        self,
        paper_set: PaperSet,
        validation_report: ValidationReport,
        template_path: Optional[Path],
        academic_year: str = "",
        course_name: str = "Generative AI",
        department: str = "",
        is_draft: bool = False,
    ) -> Path:
        """
        Export the question paper to DOCX.
        Raises ExportError if set is not APPROVED and is_draft=False.
        """
        if not is_draft and paper_set.status not in (PaperSetStatus.APPROVED, "APPROVED"):
            raise ExportError(
                f"Cannot export: set {paper_set.set_id} status is "
                f"'{paper_set.status}'. Must be APPROVED before final export."
            )

        out_dir = self._settings.drafts_dir if is_draft else self._settings.approved_dir
        filename = build_meaningful_filename(
            course_name=course_name,
            exam_type=str(paper_set.exam_type),
            set_id=paper_set.set_id,
            extension="docx",
            is_draft=is_draft,
        )

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        if template_path and template_path.exists():
            self._render_with_template(
                paper_set, template_path, out_path,
                academic_year, course_name, department, is_draft
            )
        else:
            self._render_without_template(
                paper_set, out_path, academic_year, course_name, department, is_draft
            )

        if not is_draft:
            self._record_usage(paper_set, academic_year)
            self._paper_repo.update_set_status(
                paper_set.set_id, "EXPORTED",
                exported_at=datetime.utcnow()
            )
            self._audit_repo.log(
                action="EXPORT_FINAL",
                paper_set_id=paper_set.set_id,
                details={"path": str(out_path), "academic_year": academic_year},
            )

        logger.info(f"Exported paper: {out_path}")
        return out_path

    def export_docx_bytes(
        self,
        paper_set: PaperSet,
        academic_year: str = "",
        course_name: str = "Agentic AI",
        department: str = "Department of Computer Science",
        is_draft: bool = False,
    ) -> bytes:
        """Render paper to DOCX and return raw bytes (no disk I/O)."""
        import io as _io
        from docx import Document

        doc = Document()
        _render_tabular_docx(doc, paper_set, is_draft=is_draft, course_name=course_name)

        buf = _io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def export_scheme(self, paper_set: PaperSet, is_draft: bool = False, course_name: str = "Generative AI") -> Path:
        """Export scheme of valuation."""
        out_dir = self._settings.schemes_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        base_name = build_meaningful_filename(
            course_name=course_name,
            exam_type=str(paper_set.exam_type),
            set_id=paper_set.set_id,
            extension="docx",
            is_draft=False,
        )
        filename = f"DRAFT_SCHEME_{base_name}" if is_draft else f"SCHEME_{base_name}"
        out_path = out_dir / filename
        self._render_scheme_docx(paper_set, out_path, is_draft)
        return out_path

    def export_validation_report_json(
        self, report: ValidationReport
    ) -> Path:
        """Export validation report as JSON."""
        out_dir = self._settings.validation_reports_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"validation_{report.set_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        out_path = out_dir / filename
        out_path.write_text(
            json.dumps(report.model_dump(), indent=2, default=str),
            encoding="utf-8"
        )
        return out_path

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_with_template(
        self,
        paper_set: PaperSet,
        template_path: Path,
        out_path: Path,
        academic_year: str,
        course_name: str,
        department: str,
        is_draft: bool,
    ) -> None:
        """Render paper using .docx template with placeholder substitution."""
        from docx import Document

        doc = Document(str(template_path))
        placeholders = {
            "{{UNIVERSITY_NAME}}": "Sample University",
            "{{DEPARTMENT}}": department or "Department of Computer Science",
            "{{COURSE_NAME}}": course_name,
            "{{COURSE_CODE}}": "GEN-AI-601",
            "{{EXAM_TYPE}}": self._exam_type_label(paper_set.exam_type),
            "{{DURATION}}": self._duration_label(paper_set.exam_type),
            "{{MAX_MARKS}}": self._max_marks(paper_set.exam_type),
            "{{ACADEMIC_YEAR}}": academic_year,
            "{{SET_NAME}}": paper_set.set_id,
            "{{GENERAL_INSTRUCTIONS}}": self._instructions(paper_set.exam_type),
            "{{QUESTION_BODY}}": "",  # Will be appended
        }

        # Replace placeholders in paragraphs
        for para in doc.paragraphs:
            for key, val in placeholders.items():
                if key in para.text:
                    for run in para.runs:
                        run.text = run.text.replace(key, val)

        # Add draft watermark if needed
        if is_draft:
            from docx.shared import Pt, RGBColor
            para = doc.add_paragraph()
            run = para.add_run(DRAFT_WATERMARK)
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)

        # Append question body
        self._append_questions(doc, paper_set)
        doc.save(str(out_path))

    def _render_without_template(
        self,
        paper_set: PaperSet,
        out_path: Path,
        academic_year: str,
        course_name: str,
        department: str,
        is_draft: bool,
    ) -> None:
        """Render paper from scratch without a template."""
        from docx import Document

        doc = Document()
        _render_tabular_docx(doc, paper_set, is_draft=is_draft, course_name=course_name)
        doc.save(str(out_path))

    def _append_questions(self, doc, paper_set: PaperSet) -> None:
        """Append formatted questions to document."""
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        questions = sorted(
            paper_set.questions,
            key=lambda q: (q.main_question_number, q.part)
        )

        current_main = None
        for pq in questions:
            if pq.main_question_number != current_main:
                current_main = pq.main_question_number
                q_heading = doc.add_paragraph(f"Q{pq.main_question_number}.")
                q_heading.runs[0].bold = True

            # Part line: "(a) Question text ... 10 marks"
            para = doc.add_paragraph()
            part_run = para.add_run(f"  ({pq.part}) ")
            part_run.bold = True
            para.add_run(pq.question_text)
            marks_run = para.add_run(f"  [{pq.marks} Marks]")
            marks_run.bold = True

        # Add choice instructions
        if paper_set.exam_type in (ExamType.MINOR, "MINOR"):
            doc.add_paragraph("\nAnswer any TWO full questions.")
        else:
            doc.add_paragraph("\n[See unit-wise instructions]")

    def _render_scheme_docx(self, paper_set: PaperSet, out_path: Path, is_draft: bool) -> None:
        """Render scheme of valuation to DOCX."""
        from docx import Document
        from docx.shared import RGBColor

        doc = Document()
        if is_draft:
            p = doc.add_paragraph(DRAFT_WATERMARK)
            p.runs[0].bold = True
            p.runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)

        doc.add_heading(f"Scheme of Valuation — {paper_set.set_id}", level=1)

        for pq in sorted(paper_set.questions, key=lambda q: (q.main_question_number, q.part)):
            doc.add_heading(
                f"Q{pq.main_question_number}({pq.part}): {pq.question_text[:80]}...",
                level=2
            )
            doc.add_paragraph(f"Bloom: {pq.bloom_level}  |  Source: {pq.source}  |  Marks: {pq.marks}")

            if pq.valuation_scheme:
                doc.add_paragraph("Expected Answer:")
                doc.add_paragraph(pq.valuation_scheme.expected_answer)
                doc.add_paragraph("Valuation Points:")
                for vp in pq.valuation_scheme.valuation_points:
                    doc.add_paragraph(f"  • {vp.criterion}: {vp.marks} marks")
                doc.add_paragraph(
                    f"Approval Status: {pq.valuation_scheme.approval_status}"
                )
            else:
                doc.add_paragraph("[Valuation scheme not yet generated]")
            doc.add_paragraph("—" * 40)

        doc.save(str(out_path))

    def _record_usage(self, paper_set: PaperSet, academic_year: str) -> None:
        """Record question usage in history."""
        for pq in paper_set.questions:
            qid = pq.question_id or pq.generated_id or pq.slot_id
            self._paper_repo.record_usage(
                question_id=qid,
                source=pq.source if isinstance(pq.source, str) else pq.source.value,
                paper_set_id=paper_set.set_id,
                exam_type=paper_set.exam_type if isinstance(paper_set.exam_type, str) else paper_set.exam_type.value,
                academic_year=academic_year,
            )

    def _exam_type_label(self, exam_type) -> str:
        et = exam_type if isinstance(exam_type, str) else exam_type.value
        return "Minor / Internal Examination" if et == "MINOR" else "End-Semester Examination"

    def _duration_label(self, exam_type) -> str:
        et = exam_type if isinstance(exam_type, str) else exam_type.value
        return "75 minutes" if et == "MINOR" else "180 minutes"

    def _max_marks(self, exam_type) -> str:
        et = exam_type if isinstance(exam_type, str) else exam_type.value
        return "40" if et == "MINOR" else "100"

    def _instructions(self, exam_type) -> str:
        et = exam_type if isinstance(exam_type, str) else exam_type.value
        if et == "MINOR":
            return "Answer any TWO complete questions. Each complete question carries 20 marks."
        return (
            "Unit 1 & 2: Answer any TWO complete questions from each unit. "
            "Unit 3: Answer any ONE complete question. "
            "Each complete question carries 20 marks."
        )
