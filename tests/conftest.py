"""
tests/conftest.py
Shared test fixtures and configuration.
"""

import os
import sys
import pytest
from pathlib import Path

# Point to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force test environment
os.environ["APP_ENV"] = "test"
os.environ["USE_MOCK_LLM"] = "true"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///./data/database/test_qp_agent.db"
os.environ["DEBUG"] = "true"


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize DB for each test."""
    from repositories.database import init_db
    init_db()
    yield


@pytest.fixture
def mock_llm():
    """Return mock LLM provider."""
    from services.llm_provider import MockLLMProvider
    return MockLLMProvider()


@pytest.fixture
def sample_questions():
    """Return a small list of sample Question objects for testing."""
    from models.question import Question
    from models.enums import BloomLevel, QuestionSource, ApprovalStatus

    questions = []
    unit_ch_map = {
        1: [(1, "Intro to GenAI"), (2, "Probability"), (3, "Autoencoders")],
        2: [(4, "GANs"), (5, "VAEs"), (6, "Flows")],
        3: [(7, "LLMs")],
    }
    q_count = 0
    for unit_num, chapters in unit_ch_map.items():
        for ch_num, ch_name in chapters:
            for bloom in [BloomLevel.L2, BloomLevel.L3]:
                for i in range(10):
                    q_count += 1
                    questions.append(Question(
                        question_id=f"TEST-U{unit_num}-C{ch_num}-{bloom.value}-Q{i+1:02d}",
                        course_name="Generative AI",
                        unit_number=unit_num,
                        chapter_number=ch_num,
                        chapter_name=ch_name,
                        question_text=(
                            f"Test question {q_count}: Explain {ch_name} concept "
                            f"with Bloom level {bloom.value}. Example {i+1}."
                        ),
                        bloom_level=bloom,
                        marks=10,
                        source=QuestionSource.QUESTION_BANK,
                        approval_status=ApprovalStatus.APPROVED,
                    ))
    return questions


@pytest.fixture
def loaded_bank(sample_questions):
    """Load sample questions into DB and return them."""
    from repositories.question_repo import QuestionRepository
    repo = QuestionRepository()
    repo.bulk_upsert(sample_questions)
    return sample_questions
