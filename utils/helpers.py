"""
utils/helpers.py
General utility functions.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def generate_generated_id(prefix: str = "GEN") -> str:
    """Generate a stable unique ID for AI-generated questions."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"GENAI-{prefix}-{ts}-{suffix}"


def safe_percentage(count: int, total: int, decimals: int = 2) -> float:
    """Calculate percentage safely (no division by zero)."""
    if total == 0:
        return 0.0
    return round(count / total * 100, decimals)


def truncate_text(text: str, max_len: int = 100) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def sanitize_filename(name: str) -> str:
    """Remove unsafe characters from filename."""
    name = Path(name).name
    name = re.sub(r"[^\w\-_. ]", "_", name)
    name = name.strip(". ")
    return name or "unnamed_file"


def format_bloom(bloom: str) -> str:
    """Return human-readable Bloom level label."""
    labels = {"L2": "L2 — Understand", "L3": "L3 — Apply"}
    return labels.get(bloom, bloom)


def format_source(source: str) -> str:
    """Return human-readable source label."""
    labels = {
        "QUESTION_BANK": "Question Bank",
        "AI_GENERATED": "AI Generated",
    }
    return labels.get(source, source)
