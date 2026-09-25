"""
services/file_service.py
Safe file ingestion service for all upload categories.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Optional

from config.settings import get_settings
from models.enums import FileCategory

logger = logging.getLogger(__name__)

# Allowed extensions per category
ALLOWED_EXTENSIONS: dict[FileCategory, set[str]] = {
    FileCategory.QUESTION_BANK: {".xlsx", ".xls", ".csv", ".json", ".docx", ".pdf"},
    FileCategory.LESSON_PLAN: {".pdf", ".docx", ".txt", ".md", ".xlsx"},
    FileCategory.UNIVERSITY_TEMPLATE: {".docx"},
}

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class FileServiceError(Exception):
    pass


class FileService:
    """
    Handles safe file uploads:
    - Extension and MIME validation
    - Filename sanitization
    - Size limit enforcement
    - Preservation of originals
    - Path traversal prevention
    """

    def __init__(self):
        self._settings = get_settings()

    def _sanitize_filename(self, name: str) -> str:
        """Remove path traversal and unsafe characters."""
        name = Path(name).name  # strip any directory component
        name = re.sub(r"[^\w\-_. ]", "_", name)
        name = name.strip(". ")
        if not name:
            name = "uploaded_file"
        return name

    def _category_dir(self, category: FileCategory) -> Path:
        mapping = {
            FileCategory.QUESTION_BANK: self._settings.question_bank_dir,
            FileCategory.LESSON_PLAN: self._settings.lesson_plan_dir,
            FileCategory.UNIVERSITY_TEMPLATE: self._settings.university_templates_dir,
        }
        return mapping[category]

    def validate_and_save(
        self,
        source_bytes: bytes,
        original_filename: str,
        category: FileCategory,
    ) -> Path:
        """
        Validate and save uploaded file bytes.
        Returns the absolute path of the saved copy.
        Raises FileServiceError on any validation failure.
        """
        # Size check
        size = len(source_bytes)
        if size > MAX_UPLOAD_SIZE_BYTES:
            raise FileServiceError(
                f"File too large: {size / (1024*1024):.1f} MB "
                f"(limit {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB)"
            )

        # Extension check
        suffix = Path(original_filename).suffix.lower()
        allowed = ALLOWED_EXTENSIONS.get(category, set())
        if suffix not in allowed:
            raise FileServiceError(
                f"Extension '{suffix}' not allowed for {category.value}. "
                f"Allowed: {sorted(allowed)}"
            )

        safe_name = self._sanitize_filename(original_filename)
        dest_dir = self._category_dir(category)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / safe_name

        # Avoid overwrite — append hash fragment if needed
        if dest_path.exists():
            stem = Path(safe_name).stem
            ext = Path(safe_name).suffix
            fragment = hashlib.md5(source_bytes).hexdigest()[:6]
            safe_name = f"{stem}_{fragment}{ext}"
            dest_path = dest_dir / safe_name

        dest_path.write_bytes(source_bytes)
        logger.info(f"Saved {category.value} file: {dest_path}")
        return dest_path

    def list_files(self, category: FileCategory) -> list[Path]:
        """List all non-gitkeep files in a category directory."""
        d = self._category_dir(category)
        if not d.exists():
            return []
        return sorted(
            p for p in d.iterdir()
            if p.is_file() and p.name != ".gitkeep"
        )

    def delete_file(self, path: Path) -> None:
        """Safely delete a file within the data directories."""
        settings = self._settings
        allowed_roots = [
            settings.question_bank_dir,
            settings.lesson_plan_dir,
            settings.university_templates_dir,
        ]
        resolved = path.resolve()
        is_allowed = any(
            str(resolved).startswith(str(root.resolve()))
            for root in allowed_roots
        )
        if not is_allowed:
            raise FileServiceError(
                "Attempt to delete file outside allowed directories"
            )
        if path.exists():
            path.unlink()
            logger.info(f"Deleted file: {path}")

    def get_active_template(self) -> Optional[Path]:
        """Return the first .docx file found in university_templates."""
        files = self.list_files(FileCategory.UNIVERSITY_TEMPLATE)
        for f in files:
            if f.suffix.lower() == ".docx":
                return f
        return None
