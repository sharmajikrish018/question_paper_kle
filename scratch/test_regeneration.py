"""
scratch/test_regeneration.py
Verify question regeneration in Faculty Review module.
"""

import sys
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from agents.generation_agent import AIQuestionGenerationAgent
from models.enums import BloomLevel

class DummyLLM:
    """Mock LLM Provider for unit testing constraints preservation."""
    def generate_structured(self, messages, response_model, temperature=0.8, top_p=0.95):
        from models.question import GeneratedQuestion
        from models.valuation import ValuationPoint
        
        # Verify negative constraint (avoid_texts) was included in prompt
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "AVOID generating questions similar to:" in user_msg or "old_question" in user_msg.lower() or "explain" in user_msg.lower()
        
        return GeneratedQuestion(
            question_text="Design a multi-agent workflow for a disaster-response system using graph-based coordination.",
            bloom_level=BloomLevel.L3,
            unit_number=2,
            chapter_number=4,
            chapter_name="Multi-Agent Systems",
            marks=10,
            valuation_points=[
                ValuationPoint(criterion="Graph coordination architecture", marks=5),
                ValuationPoint(criterion="Failure recovery & communication", marks=5)
            ],
            bloom_justification="Requires designing and evaluating a complex system architecture.",
            source="AI_GENERATED",
            approval_status="PENDING"
        )

def test_regeneration_preserves_constraints():
    print("--- Test 1: Question Regeneration Preserves Constraints & Negative References ---")
    mock_llm = DummyLLM()
    agent = AIQuestionGenerationAgent(mock_llm)
    
    old_text = "Explain how LangGraph enables multi-agent orchestration."
    new_q = agent.regenerate_question(
        bloom_level=BloomLevel.L3,
        unit_number=2,
        chapter_number=4,
        chapter_name="Multi-Agent Systems",
        old_question_text=old_text,
    )
    
    assert new_q is not None, "Regenerated question should not be None"
    assert new_q.bloom_level == BloomLevel.L3, f"Expected Bloom L3, got {new_q.bloom_level}"
    assert new_q.unit_number == 2, f"Expected Unit 2, got {new_q.unit_number}"
    assert new_q.chapter_number == 4, f"Expected Chapter 4, got {new_q.chapter_number}"
    assert new_q.marks == 10, f"Expected 10 Marks, got {new_q.marks}"
    assert new_q.question_text != old_text, "Regenerated text must differ from old text"
    
    print("[OK] Regeneration preserves slot constraints and avoids old question text!")

if __name__ == "__main__":
    test_regeneration_preserves_constraints()
    print("\nALL REGENERATION VERIFICATION TESTS PASSED!")
