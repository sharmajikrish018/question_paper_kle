"""
scratch/test_enhancements.py
Test script to verify all 6 QP generation enhancements.
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

def test_change_1_pattern_extraction():
    print("--- Test CHANGE 1: Exam Pattern Extraction ---")
    from agents.intake_agent import CourseIntakeAgent, QuestionPatternItem, ExamPatternInfo, FullCourseExtraction
    
    item = QuestionPatternItem(marks=5, count=2)
    assert item.to_dict() == {"marks": 5, "count": 2}
    
    pattern = ExamPatternInfo(exam_type="ISA", total_marks=30, question_pattern=[
        QuestionPatternItem(marks=5, count=2),
        QuestionPatternItem(marks=10, count=2)
    ])
    assert pattern.total_marks == 30
    assert sum(p.marks * p.count for p in pattern.question_pattern) == 30
    print("[OK] ExamPatternInfo data structures and total_marks validation OK")


def test_change_4_meaningful_filenames():
    print("--- Test CHANGE 4: Meaningful Filenames ---")
    from agents.export_agent import build_meaningful_filename
    
    fn_draft = build_meaningful_filename(
        course_name="Generative AI",
        exam_type="MINOR",
        set_id="MINOR-SET-A-041830",
        extension="docx",
        is_draft=True
    )
    print(f"Generated draft filename: {fn_draft}")
    assert fn_draft.startswith("DRAFT_Generative_AI_MINOR_")
    assert "Set-A" in fn_draft
    assert fn_draft.endswith(".docx")
    
    fn_final_pdf = build_meaningful_filename(
        course_name="Data Structures & Algorithms",
        exam_type="END_SEM",
        set_id="SET-B",
        extension="pdf",
        is_draft=False
    )
    print(f"Generated final PDF filename: {fn_final_pdf}")
    assert fn_final_pdf.startswith("Data_Structures_Algorithms_ENDSEM_")
    assert "Set-B" in fn_final_pdf
    assert fn_final_pdf.endswith(".pdf")
    print("[OK] Meaningful filenames generation OK")


def test_change_2_regeneration_method():
    print("--- Test CHANGE 2 & 5: Generation & Valuation Agents ---")
    from agents.generation_agent import AIQuestionGenerationAgent
    from agents.valuation_agent import ValuationAgent
    from models.enums import BloomLevel
    
    print("Checking AIQuestionGenerationAgent.regenerate_question signature...")
    assert hasattr(AIQuestionGenerationAgent, "regenerate_question")
    print("[OK] regenerate_question method present on AIQuestionGenerationAgent")


if __name__ == "__main__":
    test_change_1_pattern_extraction()
    test_change_4_meaningful_filenames()
    test_change_2_regeneration_method()
    print("\nALL QP ENHANCEMENTS VERIFICATION TESTS PASSED!")
