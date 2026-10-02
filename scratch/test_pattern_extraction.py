"""
scratch/test_pattern_extraction.py
Verification script for ISA and ESA examination pattern extraction.
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from agents.intake_agent import CourseIntakeAgent, _DocumentPage, ExamPatternInfo

def test_isa_paper_extraction():
    print("--- Test 1: ISA Model Question Paper Extraction ---")
    agent = CourseIntakeAgent()
    
    isa_qp_text = """
    Department of Computer Science & Engineering
    Minor Examination - Model Question Paper
    Course: Agentic AI (26ECAC401)
    Max Marks: 30
    Duration: 75 minutes

    General Instructions:
    1. Answer any TWO full questions. Each full question carries equal marks.

    Q1. (a) Explain the architecture of ReAct agents with a neat block diagram. [10 Marks]
        (b) What are tool calling protocols in LLM reasoning? [5 Marks]

    Q2. (a) Describe Memory and Planning components in Autonomous Agents. [10 Marks]
        (b) Differentiate short-term memory from long-term vector memory. [5 Marks]

    Q3. (a) Discuss multi-agent communication topology and delegation patterns. [10 Marks]
        (b) What is reflection and self-correction in AI agents? [5 Marks]
    """
    
    pages = [_DocumentPage(text=isa_qp_text, page_num=1)]
    isa_pattern, esa_pattern = agent._extract_exam_patterns(pages)
    
    assert isa_pattern is not None, "ISA pattern should be extracted"
    assert isa_pattern.total_marks == 30, f"Expected 30 total marks, got {isa_pattern.total_marks}"
    assert isa_pattern.questions_to_attempt == 2, f"Expected 2 questions to attempt, got {isa_pattern.questions_to_attempt}"
    assert isa_pattern.total_questions == 3, f"Expected 3 total questions, got {isa_pattern.total_questions}"
    assert isa_pattern.sub_question_pattern == [10, 5], f"Expected sub-pattern [10, 5], got {isa_pattern.sub_question_pattern}"
    assert isa_pattern.marks_per_full_question == 15, f"Expected 15 marks per full question, got {isa_pattern.marks_per_full_question}"
    
    print("[OK] ISA Model Question Paper extracted correctly!")
    print(f"     Extracted: {isa_pattern.to_dict()}")


def test_esa_paper_extraction():
    print("\n--- Test 2: ESA Model Question Paper Extraction ---")
    agent = CourseIntakeAgent()
    
    esa_qp_text = """
    Question Paper for End Semester Assessment (ESA)
    Max Marks: 100
    Duration: 180 minutes
    Instructions: Answer any FIVE full questions.

    1a. Describe deep neural network optimization. [10 Marks]
    1b. Explain backpropagation gradient flow. [10 Marks]

    2a. Explain convolutional layer operations. [10 Marks]
    2b. Compare Max Pooling and Average Pooling. [10 Marks]
    """
    
    pages = [_DocumentPage(text=esa_qp_text, page_num=1)]
    isa_pattern, esa_pattern = agent._extract_exam_patterns(pages)
    
    assert esa_pattern is not None, "ESA pattern should be extracted"
    assert esa_pattern.total_marks == 100, f"Expected 100 total marks, got {esa_pattern.total_marks}"
    assert esa_pattern.questions_to_attempt == 5, f"Expected 5 questions to attempt, got {esa_pattern.questions_to_attempt}"
    
    print("[OK] ESA Model Question Paper extracted correctly!")
    print(f"     Extracted: {esa_pattern.to_dict()}")


def test_fallback_warning():
    print("\n--- Test 3: Fallback Warning on Plain Text ---")
    agent = CourseIntakeAgent()
    
    plain_text_pages = [
        _DocumentPage(text="Unit 1: Introduction to Artificial Intelligence. Chapter 1 topics.", page_num=1)
    ]
    
    isa_pattern, esa_pattern = agent._extract_exam_patterns(plain_text_pages)
    
    assert isa_pattern is None, "ISA pattern should be None for plain text without QP"
    assert esa_pattern is None, "ESA pattern should be None for plain text without QP"
    
    print("[OK] Fallback handling (returning None patterns) verified cleanly!")


if __name__ == "__main__":
    test_isa_paper_extraction()
    test_esa_paper_extraction()
    test_fallback_warning()
    print("\nALL PATTERN EXTRACTION TESTS PASSED!")
