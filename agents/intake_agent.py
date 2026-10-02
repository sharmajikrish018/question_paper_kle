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
from itertools import islice
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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
class QuestionPatternItem:
    marks: int
    count: int

    def to_dict(self) -> dict:
        return {"marks": self.marks, "count": self.count}


@dataclass
class ExamPatternInfo:
    exam_type: str = "ISA"  # "ISA" or "ESA"
    total_marks: int = 30
    duration: str = ""
    instructions: str = ""
    total_questions: int = 3
    questions_to_attempt: int = 2
    marks_per_full_question: int = 15
    sub_question_pattern: list[int] = field(default_factory=list)  # e.g. [10, 5]
    question_pattern: list[QuestionPatternItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "exam_type": self.exam_type,
            "total_marks": self.total_marks,
            "duration": self.duration,
            "instructions": self.instructions,
            "total_questions": self.total_questions,
            "questions_to_attempt": self.questions_to_attempt,
            "marks_per_full_question": self.marks_per_full_question,
            "sub_question_pattern": self.sub_question_pattern,
            "question_pattern": [item.to_dict() for item in self.question_pattern],
        }


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
    # Exam patterns — ISA-I and ISA-II stored separately so faculty can edit independently
    isa1_pattern: Optional[ExamPatternInfo] = None   # ISA-I / Minor 1
    isa2_pattern: Optional[ExamPatternInfo] = None   # ISA-II / Minor 2
    esa_pattern: Optional[ExamPatternInfo] = None    # End-Semester
    exam_pattern: Optional[ExamPatternInfo] = None   # legacy alias (set to isa1_pattern value)
    # Quality
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    # Backward-compat: isa_pattern property aliases isa1_pattern
    @property
    def isa_pattern(self) -> Optional[ExamPatternInfo]:
        return self.isa1_pattern

    @isa_pattern.setter
    def isa_pattern(self, value: Optional[ExamPatternInfo]) -> None:
        self.isa1_pattern = value

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
            m = re.search(r"(?i)unit\W*(\d+|[ivx]+)\b", t)
            roman = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10}
            v = m.group(1).upper() if m else ""
            self.unit_number = int(v) if v.isdigit() else roman.get(v, 1)
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


class _SnipChapter(BaseModel):
    n: int
    title: Optional[str] = None


class _SnipSchema(BaseModel):
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    chapters: list[_SnipChapter] = Field(default_factory=list)


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

    _SNIP_META = {
        "course_name":   (r"course\s*title\s*:?", 5),
        "course_code":   (r"course\s*code\s*:?", 2),
        "department":    (r"department\s+of", 6),
        "semester":      (r"semester\s*:?", 2),
        "academic_year": (r"\byear\s*:?", 3),
    }
    _SNIP_UNIT = re.compile(r"(?i)\bunit\s*[-:]?\s*([ivx]+|\d+)\b")
    _SNIP_CH   = re.compile(r"(?i)\bchapter\s*(?:no\.?)?\s*(\d+)[.:]?")
    _SNIP_TOPIC_WORDS = 120

    @staticmethod
    def _next_words(text: str, end: int, n: int) -> str:
        return " ".join(w.group() for w in islice(re.finditer(r"\S+", text[end:]), n))

    def _scan_page(self, page: _DocumentPage) -> list:
        t, hits = page.text, []
        for field, (pat, n) in self._SNIP_META.items():
            for m in re.finditer(pat, t, re.I):
                hits.append((page.page_num, m.start(), field, "", self._next_words(t, m.end(), n)))
        for m in self._SNIP_UNIT.finditer(t):
            hits.append((page.page_num, m.start(), "unit", m.group(1), ""))
        marks = sorted([m.start() for m in self._SNIP_CH.finditer(t)] + [m.start() for m in self._SNIP_UNIT.finditer(t)])
        for m in self._SNIP_CH.finditer(t):
            nxt = next((p for p in marks if p > m.start()), len(t))
            hits.append((page.page_num, m.start(), "chapter", m.group(1),
                         self._next_words(t[:nxt], m.end(), self._SNIP_TOPIC_WORDS)))
        return hits

    def _extract_with_snippets(self, pages: list[_DocumentPage], result: FullCourseExtraction) -> None:
        with ThreadPoolExecutor(max_workers=4) as ex:
            hits = sorted(h for hs in ex.map(self._scan_page, pages) for h in hs)

        meta, chapters, seen, cur_unit = {}, [], set(), 1
        for _pg, _pos, kind, key, text in hits:
            if kind == "unit":
                cur_unit = self._parse_unit_number(key) or cur_unit
            elif kind == "chapter":
                if key not in seen:
                    seen.add(key)
                    chapters.append((cur_unit, int(key), text))
            elif kind not in meta:
                meta[kind] = text

        prompt = (
            'Return ONLY JSON: {"course_name":"","course_code":"","department":"","semester":"",'
            '"academic_year":"","chapters":[{"n":1,"title":""}]}\n'
            "Each line below is a keyword hit plus the words after it. Keep only the real value; "
            "drop trailing words belonging to the next field. Chapter title = heading only, "
            "no description, no trailing colon.\n\n"
            + "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n"
            + "\n".join(f"chapter {n}: {' '.join(t.partition(':')[0].split()[:10])}" for _, n, t in chapters) + "\n/no_think"
        )
        titles = {}
        try:
            from services.llm_provider import get_llm_provider
            r = get_llm_provider().generate_structured(
                messages=[{"role": "user", "content": prompt}],
                response_model=_SnipSchema, temperature=0.0,
            )
            logger.info(f"[IntakeAgent] snippet LLM -> {r}")
            result.course_name, result.course_code = r.course_name or None, r.course_code or None
            result.department, result.semester = r.department or None, r.semester or None
            result.academic_year = r.academic_year or None
            titles = {c.n: c.title for c in r.chapters}
        except Exception as exc:
            logger.exception(f"[IntakeAgent] snippet LLM failed: {exc}")
            for f in ("course_name", "course_code", "department", "semester", "academic_year"):
                setattr(result, f, meta.get(f))

        def _clean(v):
            return re.split(r"(?i)\b(?:course|total|duration|isa|esa|year|semester|lesson|fmth\S*)\b", v or "")[0].strip(" :-") or None
        for f in ("course_name", "course_code", "department", "semester", "academic_year"):
            if not getattr(result, f):
                setattr(result, f, _clean(meta.get(f)))

        units: dict[int, UnitInfo] = {}
        for u, n, raw in chapters:
            head, _, rest = re.sub(r"\s+\d+\s*$", "", raw).partition(":")
            rest = re.sub(r"^\s*\d+\s+|\s+\d+\s*$", "", rest)
            head = re.sub(r"^\d+\s+|\s+\d+$", "", head.strip())
            topics = [s.strip(" .") for s in rest.split(";") if s.strip(" .")]
            units.setdefault(u, UnitInfo(unit_number=u, unit_name=f"Unit {u}")).chapters.append(
                ChapterInfo(unit_number=u, chapter_number=n, title=(titles.get(n) or head).strip(" :"), topics=topics)
            )
        result.units = [units[k] for k in sorted(units)]

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

        # Extract structured data with snippet scanner + LLM
        self._extract_with_snippets(pages, result)

        # Ground truth validation & post-processing
        self._validate_and_reconcile_units(result, pages, detected_units)
        self._reconcile_minor_mapping(result, result.raw_text)

        # Extract exam patterns from model question papers in last 10 pages
        isa1_pattern, isa2_pattern, esa_pattern = self._extract_exam_patterns(pages)
        if isa1_pattern or isa2_pattern or esa_pattern:
            result.isa1_pattern = isa1_pattern
            result.isa2_pattern = isa2_pattern
            result.esa_pattern = esa_pattern
            result.exam_pattern = isa1_pattern or isa2_pattern or esa_pattern
            logger.info(
                f"[IntakeAgent] Extracted patterns — ISA-I: {isa1_pattern}, "
                f"ISA-II: {isa2_pattern}, ESA: {esa_pattern}"
            )
        else:
            logger.warning("[IntakeAgent] Examination pattern could not be confidently extracted. Preserving default pattern.")
            result.warnings.append("Examination pattern could not be confidently extracted from reference material. Using standard distribution.")

        for u in result.units:
            if not u.chapters:
                result.warnings.append(f"Unit {u.unit_number}: no chapters detected.")

        result.confidence = self._compute_confidence(result, len(detected_units))
        return result

    def _extract_exam_patterns(
        self, pages: list[_DocumentPage]
    ) -> tuple[Optional[ExamPatternInfo], Optional[ExamPatternInfo], Optional[ExamPatternInfo]]:
        """
        Locate actual model question papers (ISA-I, ISA-II, ESA) in the last 10 pages
        of the uploaded lesson plan document.

        Separately identifies:
          - ISA-I  / Minor 1 model question paper
          - ISA-II / Minor 2 model question paper
          - ESA    / End-semester model question paper

        Returns (isa1_pattern, isa2_pattern, esa_pattern).
        If ISA-I and ISA-II cannot be distinguished, the same extracted pattern
        is returned for both so faculty can edit them independently.
        """
        if not pages:
            return None, None, None

        # Always prefer the last 10 pages where model QPs typically live
        candidate_pages = pages[-10:] if len(pages) >= 10 else pages

        isa1_pages_text: list[str] = []
        isa2_pages_text: list[str] = []
        esa_pages_text:  list[str] = []

        isa1_keywords = ["isa-i", "isa 1", "isa1", "minor-i", "minor 1", "minor1", "minor exam 1",
                         "in-semester assessment i", "internal assessment i"]
        isa2_keywords = ["isa-ii", "isa 2", "isa2", "minor-ii", "minor 2", "minor2", "minor exam 2",
                         "in-semester assessment ii", "internal assessment ii"]
        isa_generic   = ["model question paper", "minor examination", "in-semester assessment",
                         "internal semester assessment", "isa"]
        esa_keywords  = ["end semester examination", "end semester assessment", "end-semester",
                         "esa", "see", "semester end examination", "question paper for end semester"]

        for p in candidate_pages:
            t = p.text.lower()
            has_qp_markers = ("max" in t or "marks" in t or "q1" in t or "question" in t)
            if not has_qp_markers:
                continue

            is_esa  = any(kw in t for kw in esa_keywords)
            is_isa1 = any(kw in t for kw in isa1_keywords)
            is_isa2 = any(kw in t for kw in isa2_keywords)
            is_isa_generic = (not is_isa1 and not is_isa2) and any(kw in t for kw in isa_generic)

            if is_esa:
                esa_pages_text.append(p.text)
            elif is_isa1:
                isa1_pages_text.append(p.text)
            elif is_isa2:
                isa2_pages_text.append(p.text)
            elif is_isa_generic:
                # Could be any ISA — add to both pools; they'll produce the same pattern
                isa1_pages_text.append(p.text)
                isa2_pages_text.append(p.text)

        # Fallback: if nothing found in last-10-pages, try all pages
        if not isa1_pages_text and not isa2_pages_text and not esa_pages_text:
            all_text = "\n".join(p.text for p in pages)
            t_lower = all_text.lower()
            if "isa" in t_lower or "minor" in t_lower or "model question paper" in t_lower:
                isa1_pages_text = [all_text]
                isa2_pages_text = [all_text]  # same source → same initial pattern
            if "esa" in t_lower or "end semester" in t_lower:
                esa_pages_text = [all_text]

        isa1_text = "\n".join(isa1_pages_text)
        isa2_text = "\n".join(isa2_pages_text)
        esa_text  = "\n".join(esa_pages_text)

        isa1_pattern = self._analyze_qp_text(isa1_text, default_exam_type="ISA-I") if isa1_text else None
        isa2_pattern = self._analyze_qp_text(isa2_text, default_exam_type="ISA-II") if isa2_text else None
        esa_pattern  = self._analyze_qp_text(esa_text,  default_exam_type="ESA")  if esa_text  else None

        # If only a generic ISA was found, replicate it as ISA-I and ISA-II
        if isa1_pattern and not isa2_pattern:
            import copy as _copy
            isa2_pattern = _copy.deepcopy(isa1_pattern)
            isa2_pattern.exam_type = "ISA-II"

        return isa1_pattern, isa2_pattern, esa_pattern


    def _analyze_qp_text(self, qp_text: str, default_exam_type: str) -> Optional[ExamPatternInfo]:
        """
        Analyze the question-paper structure:
          - Maximum marks
          - Duration
          - Instructions
          - Number of full questions & questions to attempt
          - Question numbering & sub-question marks breakdown
        """
        if not qp_text or len(qp_text.strip()) < 40:
            return None

        is_isa = "ISA" in default_exam_type.upper() or "MINOR" in default_exam_type.upper()

        # 1. Total Marks
        m_match = re.search(r"(?i)\b(?:max(?:imum)?\s*marks?|total\s*marks?|marks?)\s*[:\-=]?\s*(\d{2,3})\b", qp_text)
        total_marks = int(m_match.group(1)) if m_match else (30 if is_isa else 100)

        # 2. Duration
        d_match = re.search(r"(?i)\b(?:duration|time)\s*[:\-=]?\s*([^\n\r,;]+)", qp_text)
        duration = d_match.group(1).strip() if d_match else ("75 minutes" if is_isa else "180 minutes")

        # 3. Instructions
        instr_match = re.search(r"(?i)(?:instructions?|note)\s*[:\-=]?\s*([^\n\r]+)", qp_text)
        instructions = instr_match.group(1).strip() if instr_match else ""

        # Attempt count from instructions (e.g. "Answer any TWO full questions")
        att_match = re.search(r"(?i)\banswer\s*(?:any\s*)?(one|two|three|four|five|1|2|3|4|5)\b", qp_text)
        word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
        questions_to_attempt = word_to_num.get(att_match.group(1).lower(), 2) if att_match else (2 if is_isa else 5)

        # 4. Question & Sub-question mark extraction
        # Track marks per question and sub-parts (e.g. Q1a -> 10, Q1b -> 5)
        part_marks_map: dict[str, list[int]] = {}
        sub_marks = []
        main_questions_found = set()

        for line in qp_text.splitlines():
            # Matches "Q1a", "Q.1 (a)", "1. a)", "Q1 (a)", "Q1 a"
            q_match = re.search(r"(?i)\b(?:q|question\s*)?(\d+)\s*[\.\)]?\s*[\(\[]?([a-d])[\)\]\.]?", line)
            # Matches marks like "10 marks", "[10]", "(10)", "10M", "10 Marks"
            mark_match = re.search(r"(?i)(?:\[|\(|\b)(\d{1,2})\s*(?:marks?|m|pts)?(?:\]|\)|\b)", line)
            # More explicit marks regex
            mark_explicit = re.search(r"(?i)\b(\d{1,2})\s*(?:marks?|m)\b", line) or re.search(r"\[(\d{1,2})\]", line)

            m_val = None
            if mark_explicit:
                m_val = int(mark_explicit.group(1))
            elif mark_match and int(mark_match.group(1)) in (2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15, 16, 20):
                m_val = int(mark_match.group(1))

            if q_match:
                main_q = int(q_match.group(1))
                part_letter = q_match.group(2).lower()
                main_questions_found.add(main_q)
                if m_val is not None:
                    part_marks_map.setdefault(part_letter, []).append(m_val)
                    sub_marks.append(m_val)
            elif m_val is not None:
                # Standalone sub-question line, e.g. "a) Explain ... [10]" or "b) Derive ... [5]"
                sub_label_match = re.search(r"(?i)(?:^|[\s\(])([a-d])[\)\.]\s*", line)
                if sub_label_match:
                    part_letter = sub_label_match.group(1).lower()
                    part_marks_map.setdefault(part_letter, []).append(m_val)
                    sub_marks.append(m_val)

        total_questions = len(main_questions_found) if main_questions_found else (3 if is_isa else 8)

        # Build sub_question_pattern (e.g. a=10, b=5 -> [10, 5])
        sub_pattern = []
        if "a" in part_marks_map and "b" in part_marks_map:
            # Most common mark for part a and part b
            a_mark = max(set(part_marks_map["a"]), key=part_marks_map["a"].count)
            b_mark = max(set(part_marks_map["b"]), key=part_marks_map["b"].count)
            sub_pattern = [a_mark, b_mark]
            if "c" in part_marks_map:
                c_mark = max(set(part_marks_map["c"]), key=part_marks_map["c"].count)
                sub_pattern.append(c_mark)
        elif sub_marks:
            # Fallback: take first distinct set
            per_q = len(sub_marks) // max(1, total_questions) if total_questions > 0 else 2
            sub_pattern = sub_marks[:max(2, per_q)]

        if not sub_pattern:
            # Standard default fallback if not found in text
            if is_isa:
                sub_pattern = [10, 5] if total_marks in (30, 45) else [10, 10]
            else:
                sub_pattern = [10, 10]

        marks_per_full_q = sum(sub_pattern) if sub_pattern else (total_marks // max(1, questions_to_attempt))

        pattern_counts: dict[int, int] = {}
        for m in (sub_marks if sub_marks else sub_pattern * questions_to_attempt):
            pattern_counts[m] = pattern_counts.get(m, 0) + 1

        question_pattern_items = [
            QuestionPatternItem(marks=m, count=cnt)
            for m, cnt in pattern_counts.items()
        ]

        return ExamPatternInfo(
            exam_type=default_exam_type,
            total_marks=total_marks,
            duration=duration,
            instructions=instructions,
            total_questions=total_questions,
            questions_to_attempt=questions_to_attempt,
            marks_per_full_question=marks_per_full_q,
            sub_question_pattern=sub_pattern,
            question_pattern=question_pattern_items,
        )

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
        for p in pages:
            t = p.text.lower()
            if p.page_num == 1 or "course content" in t or "course unitization" in t:
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
                "12. Return ONLY valid JSON. No explanation, no markdown, no ```json block.\n"
                "13. minor1_unit_numbers = unit numbers having a value (not '-') in the 'Minor Exam-1' column "
                "of the unitization table; minor2_unit_numbers likewise for 'Minor Exam-2'. "
                "Example: Unit I row '1.5 - - 1.5' -> minor1 [1]. Unit numbers are integers (Unit I = 1, Unit II = 2).\n"
                "14. Chapter titles must be copied exactly from 'Chapter No N. <title>' headings without the trailing colon.\n\n"

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
                "    }\n"

                "  ],\n"

                '  "minor_configuration": {\n'
                '    "minor1_unit_numbers": [],\n'
                '    "minor2_unit_numbers": []\n'
                "  }\n"
                "}\n\n"

                "IMPORTANT:\n"
                "- The Unit 1 shown above is ONLY an example of the structure.\n"
                "- Extract the actual units and chapters from the document.\n"
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
                "Return ONLY valid JSON matching the exact structure. Extract ALL units and ALL chapters. /no_think"
            )

            response: _FullCourseSchema = llm.generate_structured(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                response_model=_FullCourseSchema,
                temperature=0.05,
            )

            result.course_name   = response.course_name   or None
            result.course_code   = response.course_code   or None
            result.department    = response.department     or None
            result.semester      = response.semester       or None
            result.academic_year = response.academic_year  or None

            result.units = []
            for u_idx, u in enumerate(response.units, start=1):
                u_num = u_idx
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

            # Allow regex fallback to run after logging the error.
            return

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
            else:
                # Copy metadata from fallback in case LLM missed it
                tmp = FullCourseExtraction(raw_text=result.raw_text)
                self._fallback_extraction(tmp)
                for f in ("course_name", "course_code", "department", "semester", "academic_year"):
                    if not getattr(result, f):
                        setattr(result, f, getattr(tmp, f))
            return

        extracted_unit_nums = {u.unit_number for u in result.units}
        missing_units = [u for u in detected_units if u not in extracted_unit_nums]

        if missing_units:
            logger.warning(
                f"[IntakeAgent] Unit count mismatch! Ground truth: {detected_units}, extracted: {sorted(list(extracted_unit_nums))}. "
                f"Missing units: {missing_units}. Running deterministic fallback for missing units."
            )
            fallback_res = FullCourseExtraction(raw_text=result.raw_text)
            self._fallback_extraction(fallback_res)

            # Copy metadata where LLM left fields empty
            for f in ("course_name", "course_code", "department", "semester", "academic_year"):
                if not getattr(result, f):
                    setattr(result, f, getattr(fallback_res, f))

            # Merge missing units from fallback_res into result
            fallback_units_dict = {u.unit_number: u for u in fallback_res.units}
            for mu in missing_units:
                if mu in fallback_units_dict:
                    result.units.append(fallback_units_dict[mu])
                else:
                    result.units.append(UnitInfo(unit_number=mu, unit_name=f"Unit {mu}"))

            result.units.sort(key=lambda u: u.unit_number)

    def _reconcile_minor_mapping(self, result: FullCourseExtraction, raw_text: str) -> None:
        mc = result.minor_configuration
        if mc.minor1 or mc.minor2:
            return
        m1, m2, cur = set(), set(), None
        num = r"(\d+(?:\.\d+)?|-)"
        for line in raw_text.splitlines():
            line = line.strip()
            u = re.fullmatch(r"(?i)unit\s*[-:]?\s*([ivx\d]+)", line)
            if u:
                cur = self._parse_unit_number(u.group(1))
                continue
            r = re.search(rf"\b\d+\s+{num}\s+{num}\s+{num}\s+{num}\s*$", line)
            if r and cur:
                if r.group(1) != "-": m1.add(cur)
                if r.group(2) != "-": m2.add(cur)
        if m1 or m2:
            result.minor_configuration = MinorConfigInfo(minor1=sorted(m1), minor2=sorted(m2))

    # ── Fallback Keyword Scanner ────────────────────────────────────────────────

    def _fallback_extraction(self, result: FullCourseExtraction) -> None:
        text = result.raw_text
        lines = text.splitlines()

        unit_pat    = re.compile(r"(?i)\b(?:unit|module)\s*[:\-_\s]*([IVX\d]+)\b(?:\s*[:\-]?\s*(.*))?")
        chapter_pat = re.compile(r"(?i)\bchapter\s*(?:no\.?)?\s*[:\-_\s]*(\d+)\s*[.:\-]?\s*(.*)")
        course_pat  = re.compile(r"(?i)course\s*(?:title|name)\s*[:\-]\s*(.+?)(?=\s+course\s*code|$)")
        code_pat    = re.compile(r"(?i)course\s*code\s*[:\-]\s*([A-Z0-9]+)")
        dept_pat    = re.compile(r"(?i)department\s*(?:of|[:\-])\s*(.+)")
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
                title = cm.group(2).strip(" :") or f"Chapter {c_num}"
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
