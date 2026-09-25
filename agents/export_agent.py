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

        if is_draft:
            out_dir = self._settings.drafts_dir
            filename = f"DRAFT_{paper_set.set_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.docx"
        else:
            out_dir = self._settings.approved_dir
            filename = f"{paper_set.set_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.docx"

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
        course_name: str = "Generative AI",
        department: str = "Department of Computer Science",
        is_draft: bool = False,
    ) -> bytes:
        """Render paper to DOCX and return raw bytes (no disk I/O)."""
        import io as _io
        from docx import Document
        from docx.shared import RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        if is_draft:
            draft_p = doc.add_paragraph(DRAFT_WATERMARK)
            draft_p.runs[0].bold = True
            draft_p.runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
            draft_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        dept_p = doc.add_paragraph(department)
        dept_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        title_p = doc.add_paragraph(
            f"{course_name} — {self._exam_type_label(paper_set.exam_type)}"
        )
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_p.runs[0].bold = True

        meta_p = doc.add_paragraph(
            f"Set: {paper_set.set_id}   |   "
            f"Time: {self._duration_label(paper_set.exam_type)}   |   "
            f"Max Marks: {self._max_marks(paper_set.exam_type)}"
            + (f"   |   Academic Year: {academic_year}" if academic_year else "")
        )
        meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph(self._instructions(paper_set.exam_type))
        doc.add_paragraph("")

        self._append_questions(doc, paper_set)

        buf = _io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def export_scheme(self, paper_set: PaperSet, is_draft: bool = False) -> Path:
        """Export scheme of valuation."""
        out_dir = self._settings.schemes_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        prefix = "DRAFT_SCHEME_" if is_draft else "SCHEME_"
        filename = f"{prefix}{paper_set.set_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.docx"
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
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        # Header
        if is_draft:
            draft_p = doc.add_paragraph(DRAFT_WATERMARK)
            draft_p.runs[0].bold = True
            draft_p.runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
            draft_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Title block
        dept_p = doc.add_paragraph(department or "Department of Computer Science")
        dept_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_p = doc.add_paragraph(f"{course_name} — {self._exam_type_label(paper_set.exam_type)}")
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_p.runs[0].bold = True

        meta_p = doc.add_paragraph(
            f"Set: {paper_set.set_id}   |   "
            f"Time: {self._duration_label(paper_set.exam_type)}   |   "
            f"Max Marks: {self._max_marks(paper_set.exam_type)}   |   "
            f"Academic Year: {academic_year}"
        )
        meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph(self._instructions(paper_set.exam_type))
        doc.add_paragraph("")

        self._append_questions(doc, paper_set)
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
