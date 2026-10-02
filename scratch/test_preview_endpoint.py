"""
scratch/test_preview_endpoint.py
Verify View Paper endpoint in papers router.
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from models.paper import PaperSet, PaperQuestion
from models.enums import ExamType, BloomLevel, QuestionSource, ApprovalStatus
from services.pdf_service import generate_paper_pdf

def test_paper_pdf_preview_rendering():
    print("--- Test: Paper PDF Preview Rendering ---")
    
    pq1 = PaperQuestion(
        slot_id="Q1a",
        main_question_number=1,
        part="a",
        unit_number=1,
        chapter_number=1,
        chapter_name="Introduction to LLM Agents",
        question_text="Explain how LangGraph enables multi-agent orchestration using researcher, planner, builder and reviewer agents.",
        bloom_level=BloomLevel.L3,
        marks=10,
        source=QuestionSource.AI_GENERATED,
        approval_status=ApprovalStatus.APPROVED,
    )
    
    pq2 = PaperQuestion(
        slot_id="Q1b",
        main_question_number=1,
        part="b",
        unit_number=1,
        chapter_number=1,
        chapter_name="Introduction to LLM Agents",
        question_text="List two key benefits of human-in-the-loop validation.",
        bloom_level=BloomLevel.L2,
        marks=5,
        source=QuestionSource.AI_GENERATED,
        approval_status=ApprovalStatus.APPROVED,
    )
    
    paper_set = PaperSet(
        set_id="PREVIEW-SET-001",
        set_index=0,
        exam_type=ExamType.MINOR,
        questions=[pq1, pq2],
    )
    
    pdf_bytes = generate_paper_pdf(paper_set, is_draft=True)
    assert pdf_bytes is not None and len(pdf_bytes) > 500, "PDF bytes should be generated"
    assert pdf_bytes.startswith(b"%PDF-"), "Should produce valid PDF bytes starting with %PDF-"
    
    print("[OK] Document PDF Preview generated cleanly from PDF Service!")

if __name__ == "__main__":
    test_paper_pdf_preview_rendering()
    print("\nALL PREVIEW RENDERING TESTS PASSED!")
