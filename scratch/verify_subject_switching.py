"""
scratch/verify_subject_switching.py — Automated verification script for Global Course Context & Subject Switching
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from repositories.subject_repo import SubjectRepository
from repositories.question_repo import QuestionRepository
from repositories.paper_repo import PaperRepository
from repositories.audit_repo import AuditRepository
from agents.coordinator import CoordinatorAgent, GenerationRequest
from models.enums import ExamType

def run_verification():
    print("=== STARTING SUBJECT SWITCHING & ISOLATION VERIFICATION ===")

    subj_repo = SubjectRepository()
    q_repo = QuestionRepository()
    p_repo = PaperRepository()

    subjects = subj_repo.list_subjects()
    print(f"1. Registered Subjects Count: {len(subjects)}")
    for s in subjects:
        print(f"   - Subject ID: '{s['subject_id']}' | Name: '{s['course_name']}' | Code: '{s['course_code']}'")

    assert len(subjects) >= 2, "FAIL: Expected at least 2 registered subjects (Agentic AI and Generative AI)"

    agentic_subj = next((s for s in subjects if "Agentic" in s["course_name"]), None)
    genai_subj = next((s for s in subjects if "Generative" in s["course_name"]), None)

    assert agentic_subj is not None, "FAIL: Agentic AI subject missing!"
    assert genai_subj is not None, "FAIL: Generative AI subject missing!"

    agentic_id = agentic_subj["subject_id"]
    genai_id = genai_subj["subject_id"]

    print("\n--- TEST 1: Agentic AI Data Scoping ---")
    agentic_detail = subj_repo.get_subject_by_slug(agentic_id)
    agentic_qs = q_repo.get_all(subject_id=agentic_id)
    print(f"Agentic AI ({agentic_id}):")
    print(f"  - Units: {len(agentic_detail.get('units', []))}")
    print(f"  - Question Bank Count: {len(agentic_qs)}")

    print("\n--- TEST 2: Generative AI Data Scoping ---")
    genai_detail = subj_repo.get_subject_by_slug(genai_id)
    genai_qs = q_repo.get_all(subject_id=genai_id)
    print(f"Generative AI ({genai_id}):")
    print(f"  - Units: {len(genai_detail.get('units', []))}")
    print(f"  - Question Bank Count: {len(genai_qs)}")

    print("\n--- TEST 3: Data Isolation Verification ---")
    agentic_ids = {q.question_id for q in agentic_qs}
    genai_ids = {q.question_id for q in genai_qs}
    intersection = agentic_ids.intersection(genai_ids)
    print(f"Agentic AI questions overlap with Generative AI questions: {len(intersection)}")
    assert len(intersection) == 0, f"FAIL: Found cross-subject question leak! Overlap: {intersection}"
    print("[OK] Subject question bank isolation verified!")

    print("\n--- TEST 4: Generation Pipeline Scoping ---")
    coord = CoordinatorAgent()
    req = GenerationRequest(
        exam_type=ExamType.MINOR,
        subject_id=genai_id,
        num_sets=1,
        selected_chapters=[1, 2, 3],
        course_name=genai_subj["course_name"],
        exclude_used_question_ids=True,
    )
    result = coord.generate(req)
    print(f"Generative AI Paper Generation Result: success={result.success}")
    assert result.success, f"FAIL: Paper generation failed: {result.errors}"

    generated_set = result.complete_paper.sets[0]
    set_id = generated_set.set_id
    print(f"Generated Set ID: {set_id} with {len(generated_set.questions)} questions")

    # Verify paper set belongs strictly to Generative AI in DB
    db_set = p_repo.get_set(set_id, subject_id=genai_id)
    assert db_set is not None, f"FAIL: Generated set {set_id} not found under subject {genai_id}!"
    print("[OK] Generated paper set correctly associated with Generative AI subject_id!")

    # Verify Agentic AI cannot query Generative AI's paper set
    cross_check = p_repo.get_set(set_id, subject_id=agentic_id)
    assert cross_check is None, f"FAIL: Cross-subject leak! Agentic AI subject queried set {set_id} from Generative AI!"
    print("[OK] Cross-subject paper query isolation verified!")

    print("\n--- TEST 5: Active Subject Switch & Persistence ---")
    subj_repo.set_active_subject_id(genai_id)
    active_now = subj_repo.get_active_subject_id()
    assert active_now == genai_id, f"FAIL: Active subject expected {genai_id}, got {active_now}"

    subj_repo.set_active_subject_id(agentic_id)
    active_switched = subj_repo.get_active_subject_id()
    assert active_switched == agentic_id, f"FAIL: Active subject switch expected {agentic_id}, got {active_switched}"
    print("[OK] Active subject context switching and persistence verified!")

    print("\n=== ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_verification()
