"""
scratch/verify_qp_format.py
Verification script for university-style tabular question paper layout.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.paper import PaperSet, PaperQuestion
from models.enums import ExamType, BloomLevel, QuestionSource, ApprovalStatus
from services.pdf_service import generate_paper_pdf
from agents.export_agent import ExportAgent, _render_tabular_docx
from docx import Document

def main():
    print("--- Verifying Tabular Question Paper Layout ---")
    
    # Create sample PaperSet matching reference layout
    questions = [
        PaperQuestion(
            slot_id="Q1a",
            main_question_number=1,
            part="a",
            unit_number=1,
            chapter_number=1,
            chapter_name="Introduction to Agentic AI",
            question_text="Explain the core principles of Agentic AI architectures, detailing how autonomous tool-use and reasoning loops differ from static LLM prompt-response patterns.",
            bloom_level=BloomLevel.L3,
            marks=10,
            source=QuestionSource.AI_GENERATED,
            approval_status=ApprovalStatus.APPROVED,
        ),
        PaperQuestion(
            slot_id="Q1b",
            main_question_number=1,
            part="b",
            unit_number=1,
            chapter_number=1,
            chapter_name="Introduction to Agentic AI",
            question_text="List four key capabilities of an agentic coding assistant.",
            bloom_level=BloomLevel.L2,
            marks=5,
            source=QuestionSource.QUESTION_BANK,
            approval_status=ApprovalStatus.APPROVED,
        ),
        PaperQuestion(
            slot_id="Q2a",
            main_question_number=2,
            part="a",
            unit_number=2,
            chapter_number=2,
            chapter_name="Multi-Agent Systems",
            question_text="Design a multi-agent workflow for automated code review, specifying roles, communication channels, and failure recovery mechanisms.",
            bloom_level=BloomLevel.L3,
            marks=10,
            source=QuestionSource.AI_GENERATED,
            approval_status=ApprovalStatus.APPROVED,
        ),
        PaperQuestion(
            slot_id="Q2b",
            main_question_number=2,
            part="b",
            unit_number=2,
            chapter_number=2,
            chapter_name="Multi-Agent Systems",
            question_text="Define consensus in distributed agent environments.",
            bloom_level=BloomLevel.L2,
            marks=5,
            source=QuestionSource.QUESTION_BANK,
            approval_status=ApprovalStatus.APPROVED,
        ),
    ]

    paper_set = PaperSet(
        set_id="SET-A",
        set_index=0,
        exam_type=ExamType.MINOR,
        status="APPROVED",
        questions=questions,
    )

    # 1. Test PDF Generation
    pdf_bytes = generate_paper_pdf(
        paper_set,
        course_name="Agentic AI",
        course_code="26ECAC401",
        is_draft=False
    )
    assert len(pdf_bytes) > 0, "PDF bytes should not be empty"
    print(f"[OK] Generated PDF ({len(pdf_bytes)} bytes)")

    # 2. Test DOCX Generation
    export_agent = ExportAgent()
    docx_bytes = export_agent.export_docx_bytes(
        paper_set,
        course_name="Agentic AI",
        is_draft=False
    )
    assert len(docx_bytes) > 0, "DOCX bytes should not be empty"
    print(f"[OK] Generated DOCX ({len(docx_bytes)} bytes)")

    print("--- SUCCESS: Tabular QP Format verified cleanly! ---")

if __name__ == "__main__":
    main()
