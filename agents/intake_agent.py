"""
agents/intake_agent.py
Loads and extracts structured information from course material files.

Extraction strategy:
  1. Read PDF/DOCX/TXT/Excel into structured per-page representations (_DocumentPage)
  2. Perform ground-truth regex detection of metadata, units, and assessment sections
  3. Prioritize essential pages (Cover/Metadata, Course Content/Syllabus, Assessment)
  4. Semantically rank additional paragraphs using sentence-transformer embeddings
  5. Call Qwen via generate_structured() with instructions to extract ALL units and minor mappings
  6. Validate Qwen output against ground-truth unit count; merge missing units if necessary
  7. Compute robust confidence score based on metadata, unit completeness, and detail
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Union

from pydantic import BaseModel, ConfigDict, Field, AliasChoices, model_validator

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────────

_PAGE_LIMIT = 10
_CHUNK_MAX_CHARS = 16000   # Text fed to LLM after section assembly


# ── Domain types ───────────────────────────────────────────────────────────────

@dataclass
class ChapterInfo:
    unit_number: int
    chapter_number: int
    title: str
    topics: list[str] = field(default_factory=list)


@dataclass
class UnitInfo:
    unit_number: int
    unit_name: str
    chapters: list[ChapterInfo] = field(default_factory=list)


@dataclass
class MinorConfigInfo:
    minor1: list[int] = field(default_factory=list)  # unit numbers for Minor 1
    minor2: list[int] = field(default_factory=list)  # unit numbers for Minor 2


@dataclass
class FullCourseExtraction:
    """Full structured extraction result from an LP document."""
    raw_text: str = ""
    # Course info — None means not found in LP (never fabricated)
    course_name: Optional[str]     = None
    course_code: Optional[str]     = None
    department:  Optional[str]     = None
    semester:    Optional[str]     = None
    academic_year: Optional[str]   = None
    # Structure
    units: list[UnitInfo] = field(default_factory=list)
    minor_configuration: MinorConfigInfo = field(default_factory=MinorConfigInfo)
    # Quality
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    # Backward-compat: flat chapter list derived from units
    @property
    def chapters(self) -> list[ChapterInfo]:
        result = []
        for u in self.units:
            result.extend(u.chapters)
        return result


# Legacy alias
LessonPlanExtraction = FullCourseExtraction


@dataclass
class _DocumentPage:
    page_num: int   # 1-based
    text: str


# ── LLM response schema ────────────────────────────────────────────────────────

class _ChapterSchema(BaseModel):
    unit_number: Optional[int] = Field(default=None, validation_alias=AliasChoices("unit_number", "unitNumber"))
    chapter_number: Union[int, str] = Field(default=1, validation_alias=AliasChoices("chapterNumber", "chapter_number"))
    title: str = Field(default="", validation_alias=AliasChoices("title", "chapter_title"))
    topics: list[str] = Field(default_factory=list)


class _UnitSchema(BaseModel):
    unit_number: Optional[int] = Field(default=None, validation_alias=AliasChoices("unit_number", "unitNumber"))
    unit_name: Optional[str] = Field(default=None, validation_alias=AliasChoices("unit_name", "unit_title"))
    title: Optional[str] = Field(default=None, validation_alias=AliasChoices("title", "unit_name"))
    chapters: list[_ChapterSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def parse_unit_num(self):
        if self.unit_number is None:
            t = self.title or self.unit_name or ""
            m = re.search(r"(\d+)", t)
            if m:
                self.unit_number = int(m.group(1))
            else:
                self.unit_number = 1
        if not self.unit_name:
            self.unit_name = self.title or f"Unit {self.unit_number}"
        return self


class _MinorConfigSchema(BaseModel):
    minor1_unit_numbers: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices("minor1_unit_numbers", "minor1UnitNumbers")
    )
    minor2_unit_numbers: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices("minor2_unit_numbers", "minor2UnitNumbers")
    )


class _FullCourseSchema(BaseModel):
    """JSON schema returned by Qwen for full course extraction."""
    course_name:   Optional[str] = Field(None, validation_alias=AliasChoices("course_name", "courseName"))
    course_code:   Optional[str] = Field(None, validation_alias=AliasChoices("course_code", "courseCode"))
    department:    Optional[str] = Field(None)
    semester:      Optional[str] = Field(None)
    academic_year: Optional[str] = Field(None, validation_alias=AliasChoices("academic_year", "academicYear"))
    units: list[_UnitSchema] = Field(
        default_factory=list,
        description="COMPLETE list of ALL units found in the LP with their chapters"
    )
    minor_configuration: _MinorConfigSchema = Field(
        default_factory=_MinorConfigSchema,
        validation_alias=AliasChoices("minor_configuration", "minorConfiguration")
    )


# ── Main agent ─────────────────────────────────────────────────────────────────

class CourseIntakeAgent:
    """
    Extracts course information and structure from lesson plan files using Qwen.
    Supports PDF, DOCX, TXT, and Excel formats with format-specific page readers.
    """

    _STRUCTURE_QUERY = (
        "course units chapters modules syllabus lesson plan topics learning outcomes "
        "course name code department semester year minor exam 1 minor exam 2"
    )

    # ── Public entry point ─────────────────────────────────────────────────────

    def extract_lesson_plan(
        self,
        path: Path,
        page_limit: int = _PAGE_LIMIT,
    ) -> FullCourseExtraction:
        """
        Extract text from a lesson plan file and parse course structure with Qwen.
        """
        result = FullCourseExtraction()
        pages = self._read_document_pages(path, page_limit=page_limit)

        if not pages:
            result.warnings.append(f"No text could be extracted from {path.name}.")
            return result

        result.raw_text = "\n\n--- Page Break ---\n\n".join(
            f"[Page {p.page_num}]\n{p.text}" for p in pages
        )

        # Detect ground truth unit numbers via regex pre-scan
        detected_units = self._detect_ground_truth_units(pages)
        logger.info(f"[IntakeAgent] Detected ground-truth unit numbers: {detected_units}")

        # Assemble prioritized text context for Qwen
        relevant_text = self._assemble_relevant_context(pages)

        # Extract structured data with Qwen
        self._extract_with_llm(relevant_text, result, detected_units)

        # Ground truth validation & post-processing
        self._validate_and_reconcile_units(result, pages, detected_units)
        self._reconcile_minor_mapping(result, result.raw_text)

        result.confidence = self._compute_confidence(result, len(detected_units))
        return result

    # ── Multi-format Readers ───────────────────────────────────────────────────

    def _read_document_pages(self, path: Path, page_limit: int) -> list[_DocumentPage]:
        suffix = path.suffix.lower()
        try:
            if suffix == ".pdf":
                return self._read_pdf_pages(path, page_limit)
            elif suffix == ".docx":
                return self._read_docx_pages(path, page_limit)
            elif suffix in {".txt", ".md"}:
                return self._read_txt_pages(path, page_limit)
            elif suffix in {".xlsx", ".xls"}:
                return self._read_excel_pages(path)
            else:
                logger.warning(f"Unsupported format: {suffix}")
                return []
        except Exception as exc:
            logger.warning(f"Failed to read file {path}: {exc}")
            return []

    def _read_pdf_pages(self, path: Path, page_limit: int) -> list[_DocumentPage]:
        pages = []
        # 1. Try pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                for idx, page in enumerate(pdf.pages[:page_limit]):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(_DocumentPage(page_num=idx + 1, text=text))
            if pages:
                return pages
        except Exception as exc:
            logger.debug(f"pdfplumber extraction failed: {exc}")

        # 2. Try pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            for idx, page in enumerate(reader.pages[:page_limit]):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(_DocumentPage(page_num=idx + 1, text=text))
            if pages:
                return pages
        except Exception as exc:
            logger.debug(f"pypdf extraction failed: {exc}")

        # 3. Try PyPDF2
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(path))
            for idx, page in enumerate(reader.pages[:page_limit]):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(_DocumentPage(page_num=idx + 1, text=text))
            if pages:
                return pages
        except Exception as exc:
            logger.debug(f"PyPDF2 extraction failed: {exc}")

        # 4. Try fitz (PyMuPDF)
        try:
            import fitz
            doc = fitz.open(str(path))
            for idx, page in enumerate(doc[:page_limit]):
                text = page.get_text() or ""
                if text.strip():
                    pages.append(_DocumentPage(page_num=idx + 1, text=text))
            if pages:
                return pages
        except Exception as exc:
            logger.debug(f"fitz extraction failed: {exc}")

        return pages

    def _read_docx_pages(self, path: Path, page_limit: int) -> list[_DocumentPage]:
        from docx import Document
        doc = Document(str(path))
        elements = []
        for p in doc.paragraphs:
            if p.text.strip():
                elements.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_str = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_str:
                    elements.append(f"[Table Row] {row_str}")

        pages = []
        chunk_size = 40
        for i in range(0, min(len(elements), page_limit * chunk_size), chunk_size):
            chunk_text = "\n".join(elements[i:i + chunk_size])
            pages.append(_DocumentPage(page_num=(i // chunk_size) + 1, text=chunk_text))
        return pages

    def _read_txt_pages(self, path: Path, page_limit: int) -> list[_DocumentPage]:
        raw = path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        pages = []
        chunk_size = 50
        for i in range(0, min(len(lines), page_limit * chunk_size), chunk_size):
            chunk_text = "\n".join(lines[i:i + chunk_size])
            pages.append(_DocumentPage(page_num=(i // chunk_size) + 1, text=chunk_text))
        return pages

    def _read_excel_pages(self, path: Path) -> list[_DocumentPage]:
        import pandas as pd
        df = pd.read_excel(path, dtype=str)
        text = df.to_string(index=False)
        return [_DocumentPage(page_num=1, text=text)]

    # ── Ground Truth Detection & Context Assembly ──────────────────────────────

    def _detect_ground_truth_units(self, pages: list[_DocumentPage]) -> list[int]:
        """Detect unit numbers via regex scan across all pages."""
        unit_nums = set()
        pattern = re.compile(r"(?i)\b(?:unit|module)\s*[:\-_\s]*([IVX\d]+)\b")
        for page in pages:
            matches = pattern.findall(page.text)
            for m in matches:
                val = self._parse_unit_number(m)
                if val is not None and 1 <= val <= 20:
                    unit_nums.add(val)
        return sorted(list(unit_nums))

    @staticmethod
    def _parse_unit_number(val: str) -> Optional[int]:
        val = val.strip().upper()
        if val.isdigit():
            return int(val)
        roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
        return roman_map.get(val)

    def _assemble_relevant_context(self, pages: list[_DocumentPage], max_chars: int = _CHUNK_MAX_CHARS) -> str:
        """
        Build text for LLM ensuring Metadata (Page 1/2), Course Content, and Assessment
        pages are always included.
        """
        full_text = "\n\n".join(p.text for p in pages)
        if len(full_text) <= max_chars:
            return full_text

        priority_pages = set()
        # Page 1 & 2 are metadata candidates
        for p in pages:
            if p.page_num <= 2:
                priority_pages.add(p.page_num)

            lower_text = p.text.lower()
            if any(k in lower_text for k in ["course content", "syllabus", "unit -", "unit 1", "unit i"]):
                priority_pages.add(p.page_num)
            if any(k in lower_text for k in ["assessment", "minor exam", "cie", "unitization"]):
                priority_pages.add(p.page_num)

        selected_pages = [p for p in pages if p.page_num in priority_pages]
        assembled_text = "\n\n".join(f"[Page {p.page_num}]\n{p.text}" for p in selected_pages)

        if len(assembled_text) <= max_chars:
            return assembled_text

        # Fallback to paragraph semantic ranking if prioritized assembled text is still huge
        return self._select_relevant_chunks(assembled_text, max_chars)

    def _select_relevant_chunks(self, text: str, max_chars: int = _CHUNK_MAX_CHARS) -> str:
        _UNIT_RE = re.compile(r"(?i)\bunit\s*[:\-_\s]*[ivx\d]+\b")
        paragraphs = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) > 30 or _UNIT_RE.search(p)]
        if not paragraphs:
            return text[:max_chars]

        try:
            from sentence_transformers import SentenceTransformer
            from concurrent.futures import ThreadPoolExecutor

            model = SentenceTransformer("all-MiniLM-L6-v2")
            with ThreadPoolExecutor(max_workers=2) as pool:
                query_future = pool.submit(
                    model.encode,
                    [self._STRUCTURE_QUERY],
                    normalize_embeddings=True,
                )
                para_future = pool.submit(
                    model.encode,
                    paragraphs,
                    normalize_embeddings=True,
                    batch_size=32,
                )
                query_emb = query_future.result()[0]
                para_embs = para_future.result()

            scores = para_embs @ query_emb
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

            must_include = set(range(min(5, len(paragraphs))))
            selected_indices = sorted(must_include | {idx for idx, _ in ranked[:25]})

            selected = "\n\n".join(paragraphs[i] for i in selected_indices)
            return selected[:max_chars]

        except Exception as exc:
            logger.warning(f"[IntakeAgent] Sentence Transformer ranking fallback: {exc}")
            return text[:max_chars]

    # ── LLM Extraction ─────────────────────────────────────────────────────────

    def _extract_with_llm(
        self,
        relevant_text: str,
        result: FullCourseExtraction,
        detected_units: list[int],
    ) -> None:
        try:
            from services.llm_provider import get_llm_provider
            llm = get_llm_provider()

            system_prompt = (
                "You are an expert academic document parser.\n"
                "Your task is to extract structured course details, units, chapters, and minor exam mappings "
                "from a university lesson plan.\n\n"

                "STRICT RULES FOR OUTPUT:\n"
                "1. Extract ALL units and ALL chapters present in the document.\n"
                "2. Never stop after Unit 1 or Unit 2.\n"
                "3. Do NOT assume a fixed number of units or chapters. "
                "If the document has Unit 3, extract Unit 3. If it has Unit 4, extract Unit 4, and so on.\n"
                "4. Unit titles MUST use the field name `title`.\n"
                "5. Chapter numbers MUST use the field name `chapterNumber`.\n"
                "6. Chapter titles MUST use the field name `title`.\n"
                "7. Chapter numbers should be strings exactly as they appear in the document, "
                "for example \"1\", \"2\", \"3\", \"4\".\n"
                "8. Do NOT use `unit_number`, `unit_name`, `chapter_number`, or `chapter_title`.\n"
                "9. Do NOT add extra fields that are not shown in the required structure.\n"
                "10. Preserve the parent-child hierarchy: every chapter must remain inside its correct unit.\n"
                "11. Minor exam mappings must be extracted from the LP text and must NOT be hardcoded.\n"
                "12. Return ONLY valid JSON. No explanation, no markdown, no ```json block.\n\n"

                "RETURN JSON IN EXACTLY THIS STRUCTURE:\n\n"

                "{\n"
                '  "course_name": "Actual course name from document",\n'
                '  "course_code": "Actual course code from document",\n'
                '  "department": "Actual department from document",\n'
                '  "semester": "Actual semester from document",\n'
                '  "academic_year": "Actual academic year from document",\n'
                '  "units": [\n'

                "    {\n"
                '      "title": "Unit - 1",\n'
                '      "chapters": [\n'
                "        {\n"
                '          "chapterNumber": "1",\n'
                '          "title": "Actual Chapter 1 title from document"\n'
                "        },\n"
                "        {\n"
                '          "chapterNumber": "2",\n'
                '          "title": "Actual Chapter 2 title from document"\n'
                "        }\n"
                "      ]\n"
                "    },\n"

                "    {\n"
                '      "title": "Unit - 2",\n'
                '      "chapters": [\n'
                "        {\n"
                '          "chapterNumber": "3",\n'
                '          "title": "Actual Chapter 3 title from document"\n'
                "        },\n"
                "        {\n"
                '          "chapterNumber": "4",\n'
                '          "title": "Actual Chapter 4 title from document"\n'
                "        }\n"
                "      ]\n"
                "    },\n"

                "    {\n"
                '      "title": "Unit - 3",\n'
                '      "chapters": [\n'
                "        {\n"
                '          "chapterNumber": "5",\n'
                '          "title": "Actual Chapter 5 title from document"\n'
                "        },\n"
                "        {\n"
                '          "chapterNumber": "6",\n'
                '          "title": "Actual Chapter 6 title from document"\n'
                "        }\n"
                "      ]\n"
                "    }\n"

                "  ],\n"

                '  "minor_configuration": {\n'
                '    "minor1_unit_numbers": [],\n'
                '    "minor2_unit_numbers": []\n'
                "  }\n"
                "}\n\n"

                "IMPORTANT:\n"
                "- The Unit 1, Unit 2, Unit 3 shown above are ONLY examples of the structure.\n"
                "- Extract the actual units and chapters from the document.\n"
                "- If Unit 3 does not exist in the document, DO NOT create Unit 3.\n"
                "- If Unit 3 exists, include it with ALL of its chapters.\n"
                "- Follow the exact field names and hierarchy shown above."
            )

            units_str = ", ".join(map(str, detected_units)) if detected_units else "all units listed in syllabus"
            user_prompt = (
                f"Extract complete course information, units, chapters, and minor exam mapping from the lesson plan text below.\n\n"
                f"Detected Ground-Truth Units in Document: {detected_units or 'At least 1'}\n"
                f"You MUST extract ALL of these units ({units_str}).\n\n"
                "LESSON PLAN TEXT:\n"
                "---\n"
                f"{relevant_text}\n"
                "---\n\n"
                "Return ONLY valid JSON matching the exact structure. Extract ALL units and ALL chapters."
            )

            response: _FullCourseSchema = llm.generate_structured(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                response_model=_FullCourseSchema,
                temperature=0.05,
                max_tokens=4096,
            )

            result.course_name   = response.course_name   or None
            result.course_code   = response.course_code   or None
            result.department    = response.department     or None
            result.semester      = response.semester       or None
            result.academic_year = response.academic_year  or None

            result.units = []
            for u_idx, u in enumerate(response.units, start=1):
                u_num = u.unit_number or u_idx
                u_name = u.title or u.unit_name or f"Unit {u_num}"
                ch_objs = []
                for ch_idx, ch in enumerate(u.chapters, start=1):
                    c_num = int(ch.chapter_number) if (isinstance(ch.chapter_number, int) or (isinstance(ch.chapter_number, str) and ch.chapter_number.isdigit())) else ch_idx
                    ch_objs.append(
                        ChapterInfo(
                            unit_number=u_num,
                            chapter_number=c_num,
                            title=ch.title,
                            topics=ch.topics if hasattr(ch, "topics") and ch.topics else [],
                        )
                    )
                unit = UnitInfo(
                    unit_number=u_num,
                    unit_name=u_name,
                    chapters=ch_objs,
                )
                result.units.append(unit)

            result.minor_configuration = MinorConfigInfo(
                minor1=response.minor_configuration.minor1_unit_numbers,
                minor2=response.minor_configuration.minor2_unit_numbers,
            )

            logger.info(
                f"[IntakeAgent] Qwen extracted {len(result.units)} units, "
                f"{len(result.chapters)} chapters"
            )

        except Exception as exc:
            import json
            import sys
            import traceback

            raw_response = getattr(exc, "raw_response", None)
            if raw_response is None and exc.__cause__:
                raw_response = getattr(exc.__cause__, "raw_response", None)

            raw_json = getattr(exc, "raw_json", None)
            if raw_json is None and exc.__cause__:
                raw_json = getattr(exc.__cause__, "raw_json", None)

            cause = exc.__cause__ or exc

            err_details = [
                "=" * 80,
                "!!! DEBUG: QWEN JSON VALIDATION FAILURE DETECTED !!!",
                f"1. Exception Type: {type(exc).__name__} (Cause: {type(cause).__name__})",
                f"2. Exception Message:\n{exc}",
                f"3. Full Traceback:\n{traceback.format_exc()}",
                f"4. Raw LLM Response:\n{raw_response if raw_response is not None else 'N/A'}",
                f"5. Response Type: {type(response) if 'response' in locals() else 'None'}",
                f"6. Generated JSON Schema:\n{json.dumps(_FullCourseSchema.model_json_schema(), indent=2)}",
                f"7. Raw Parsed JSON (if any):\n{json.dumps(raw_json, indent=2) if raw_json is not None else 'N/A'}",
                "=" * 80
            ]
            full_log_str = "\n".join(err_details)
            logger.error(full_log_str)
            print(full_log_str, file=sys.stderr)

            # Do NOT silently call fallback before we see the actual error. Re-raise exception.
            raise exc

    # ── Reconciliation & Ground Truth Validation ───────────────────────────────

    def _validate_and_reconcile_units(
        self,
        result: FullCourseExtraction,
        pages: list[_DocumentPage],
        detected_units: list[int],
    ) -> None:
        """If Qwen missed any ground truth units, use deterministic regex fallback to restore them."""
        if not detected_units:
            if not result.units:
                self._fallback_extraction(result)
            return

        extracted_unit_nums = {u.unit_number for u in result.units}
        missing_units = [u for u in detected_units if u not in extracted_unit_nums]

        if missing_units:
            logger.warning(
                f"[IntakeAgent] Unit count mismatch! Ground truth: {detected_units}, Qwen: {sorted(list(extracted_unit_nums))}. "
                f"Missing units: {missing_units}. Running deterministic fallback for missing units."
            )
            result.warnings.append(
                f"Qwen omitted Unit(s) {missing_units}. Restored missing unit structure from document source."
            )
            fallback_res = FullCourseExtraction(raw_text=result.raw_text)
            self._fallback_extraction(fallback_res)

            # Merge missing units from fallback_res into result
            fallback_units_dict = {u.unit_number: u for u in fallback_res.units}
            for mu in missing_units:
                if mu in fallback_units_dict:
                    result.units.append(fallback_units_dict[mu])
                else:
                    result.units.append(UnitInfo(unit_number=mu, unit_name=f"Unit {mu}"))

            result.units.sort(key=lambda u: u.unit_number)

    def _reconcile_minor_mapping(self, result: FullCourseExtraction, raw_text: str) -> None:
        """If Minor exam mapping is empty, perform regex fallback on raw text."""
        m1 = result.minor_configuration.minor1
        m2 = result.minor_configuration.minor2

        if not m1 and not m2:
            m1_units = set()
            m2_units = set()

            # Scan for Minor Exam-1 / Minor 1
            m1_match = re.search(r"(?i)minor\s*(?:exam\s*)?[\-_\s]*1.*?(?:unit[s\s\-\d&,]+)", raw_text)
            if m1_match:
                found = re.findall(r"(?i)\bunit\s*[\-:]?\s*(\d+)", m1_match.group(0))
                for u in found:
                    m1_units.add(int(u))

            # Scan for Minor Exam-2 / Minor 2
            m2_match = re.search(r"(?i)minor\s*(?:exam\s*)?[\-_\s]*2.*?(?:unit[s\s\-\d&,]+)", raw_text)
            if m2_match:
                found = re.findall(r"(?i)\bunit\s*[\-:]?\s*(\d+)", m2_match.group(0))
                for u in found:
                    m2_units.add(int(u))

            if m1_units or m2_units:
                result.minor_configuration = MinorConfigInfo(
                    minor1=sorted(list(m1_units)),
                    minor2=sorted(list(m2_units)),
                )

    # ── Fallback Keyword Scanner ────────────────────────────────────────────────

    def _fallback_extraction(self, result: FullCourseExtraction) -> None:
        text = result.raw_text
        lines = text.splitlines()

        unit_pat    = re.compile(r"(?i)\b(?:unit|module)\s*[:\-_\s]*([IVX\d]+)\b(?:\s*[:\-]?\s*(.*))?")
        chapter_pat = re.compile(r"(?i)(?:chapter|module|topic)\s*[:\-_\s]*(\d+)\s*[:\-]?\s*(.*)")
        course_pat  = re.compile(r"(?i)course\s*(?:title|name)\s*[:\-]\s*(.+)")
        code_pat    = re.compile(r"(?i)course\s*code\s*[:\-]\s*([A-Z0-9]+)")
        dept_pat    = re.compile(r"(?i)department\s*[:\-]\s*(.+)")
        sem_pat     = re.compile(r"(?i)semester\s*[:\-]\s*(\d+)")
        year_pat    = re.compile(r"(?i)(?:academic\s*year|year)\s*[:\-]\s*(\d{4}[–\-]\d{2,4})")

        current_unit_num = 1
        global_chap_idx = 0
        units_dict: dict[int, UnitInfo] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if result.course_name is None:
                m = course_pat.search(line)
                if m: result.course_name = m.group(1).strip()
            if result.course_code is None:
                m = code_pat.search(line)
                if m: result.course_code = m.group(1).strip()
            if result.department is None:
                m = dept_pat.search(line)
                if m: result.department = m.group(1).strip()
            if result.semester is None:
                m = sem_pat.search(line)
                if m: result.semester = m.group(1).strip()
            if result.academic_year is None:
                m = year_pat.search(line)
                if m: result.academic_year = m.group(1).strip()

            um = unit_pat.search(line)
            if um:
                u_num = self._parse_unit_number(um.group(1))
                if u_num:
                    current_unit_num = u_num
                    u_title = (um.group(2) or "").strip() or f"Unit {current_unit_num}"
                    if current_unit_num not in units_dict:
                        units_dict[current_unit_num] = UnitInfo(
                            unit_number=current_unit_num, unit_name=u_title
                        )
                    continue

            cm = chapter_pat.search(line)
            if cm:
                global_chap_idx += 1
                c_num = int(cm.group(1)) if cm.group(1).isdigit() else global_chap_idx
                title = cm.group(2).strip() or f"Chapter {c_num}"
                if current_unit_num not in units_dict:
                    units_dict[current_unit_num] = UnitInfo(
                        unit_number=current_unit_num, unit_name=f"Unit {current_unit_num}"
                    )
                units_dict[current_unit_num].chapters.append(
                    ChapterInfo(unit_number=current_unit_num, chapter_number=c_num, title=title)
                )

        result.units = [units_dict[k] for k in sorted(units_dict.keys())]

    # ── Confidence Calculator ──────────────────────────────────────────────────

    def _compute_confidence(self, result: FullCourseExtraction, detected_units_count: int = 0) -> float:
        if not result.raw_text:
            return 0.0

        info_fields = sum([
            bool(result.course_name),
            bool(result.course_code),
            bool(result.department),
            bool(result.semester),
            bool(result.academic_year),
        ])

        meta_score = info_fields * 0.08  # up to 0.40

        units_count = len(result.units)
        if detected_units_count > 0:
            unit_ratio = min(1.0, units_count / detected_units_count)
        else:
            unit_ratio = 1.0 if units_count > 0 else 0.0
        unit_score = unit_ratio * 0.45   # up to 0.45

        has_chapters = len(result.chapters) > 0
        has_topics = any(ch.topics for ch in result.chapters)
        detail_score = (0.10 if has_chapters else 0.0) + (0.05 if has_topics else 0.0)  # up to 0.15

        confidence = round(meta_score + unit_score + detail_score, 2)
        return min(1.0, confidence)
