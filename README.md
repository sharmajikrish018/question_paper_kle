# Prashnopatra — AI Question Paper Agent

> ⚠️ **CONFIDENTIAL** — Question papers are restricted academic documents. Do not distribute or commit generated output files.

**Prashnopatra** is an agentic system that assists university faculty in generating compliant, validated question papers for the **Generative AI** course. It sources questions from an approved question bank (~70%) and generates the remainder via LLM (~30%), enforces Bloom taxonomy compliance, routes papers through a faculty approval gate, and exports to DOCX and PDF.

The system is a **faculty coordination assistant**, not an autonomous authority. No paper becomes final until explicitly approved by faculty.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [Usage Workflow](#usage-workflow)
- [Examination Patterns](#examination-patterns)
- [Question Bank Schema](#question-bank-schema)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
Browser (Next.js 16)
        │  HTTP / REST
        ▼
FastAPI + Uvicorn  (api/)
        │
        ▼
CoordinatorAgent  (agents/coordinator.py)
│
├── IntakeAgent          — Extracts chapter/unit structure from lesson plan PDF/DOCX
├── QuestionBankAgent    — Validates, normalises, deduplicates the approved bank
├── BlueprintAgent       — Converts UI parameters into an immutable generation blueprint
├── SelectionAgent       — Greedy constraint-based bank question selection
├── GenerationAgent      — LLM-powered question generation grounded in lesson plan
├── SimilarityAgent      — Layered duplicate detection (exact → TF-IDF → embeddings)
├── CompositionAgent     — Assigns questions to Q1(a)/Q1(b)/… slots
├── ValuationAgent       — Generates 10-mark scheme per question via LLM
├── ValidationAgent      — Rules-based paper validation (PASS / WARN / FAIL)
└── ExportAgent          — DOCX + PDF export with faculty-approval gate
```

**Only** generation, semantic classification, and valuation tasks call the LLM.  
All arithmetic, slot assignment, duplicate detection, validation, and approval enforcement is deterministic Python.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16 (App Router), TypeScript, Vanilla CSS (or Streamlit UI via `app.py`) |
| **Backend** | FastAPI, Uvicorn, Python 3.11+ |
| **Database** | SQLite via SQLAlchemy 2.0 |
| **LLM Provider** | OpenAI-compatible API (**Ollama**, Groq, OpenRouter, NVIDIA NIM, Custom Endpoint, or Mock) |
| **LLM Models** | **Qwen 2.5** (`qwen2.5:7b`, `qwen2.5-coder`), **LLaMA 3.3**, GPT-4o, etc. |
| **Local LLM Client** | `ollama` Python SDK & local REST server (`http://localhost:11434/v1`) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) |
| **Document Parsing**| PyMuPDF (`fitz`), `pdfplumber`, `pypdf`, `python-docx`, `openpyxl`, `pandas` |
| **PDF Export** | ReportLab |
| **DOCX Export** | python-docx |
| **Validation** | Pydantic v2, pydantic-settings |

---

## Prerequisites

- **Python 3.11+** — [python.org](https://python.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Ollama** *(Optional — for 100% local, offline execution with Qwen models)* — [ollama.com](https://ollama.com)
- **Groq API key** *(Optional free cloud inference)* — [console.groq.com](https://console.groq.com)
- Or run in **Mock mode** (no API key or local model required)

---

## Setup

### 1 — Clone and enter the project

```powershell
cd D:\sdgsgddgsgsdg\Prashnopatra
```

### 2 — Create and activate the Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If you get an execution policy error, run first:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

### 3 — Install Python dependencies

Includes core API libraries, `ollama`, `PyMuPDF`, `pdfplumber`, `reportlab`, `sentence-transformers`, etc.:

```powershell
pip install -r requirements.txt
```

### 4 — Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### 5 — Configure environment variables

```powershell
copy .env.example .env
notepad .env
```

---

## Configuration

All settings live in `.env`. Key LLM provider options:

### Local LLM via Ollama & Qwen (100% Offline & Free)

To run fully local question paper generation using **Qwen 2.5** via **Ollama**:

1. Install Ollama from [ollama.com](https://ollama.com) and pull a Qwen model:
   ```powershell
   ollama pull qwen2.5:7b
   ```
2. Configure `.env`:
   ```dotenv
   LLM_PROVIDER="ollama"
   OLLAMA_MODEL="qwen2.5:7b"
   OLLAMA_BASE_URL="http://localhost:11434/v1"
   OLLAMA_API_KEY="ollama"
   ```

*(You can also use `qwen2.5:14b`, `qwen2.5-coder:7b`, or `qwen2.5:72b` depending on your hardware).*

### Groq Cloud Provider

```dotenv
LLM_PROVIDER="groq"
LLM_MODEL="llama-3.3-70b-versatile"
GROQ_API_KEY="your-groq-key"
```

### OpenRouter (with Qwen or GPT-4o)

```dotenv
LLM_PROVIDER="openrouter"
OPENROUTER_API_KEY="your-key"
OPENROUTER_MODEL="qwen/qwen-2.5-72b-instruct"
```

### NVIDIA NIM (alternative)

```dotenv
LLM_PROVIDER="nvidia_nim"
NVIDIA_NIM_API_KEY="your-key"
NVIDIA_NIM_MODEL="meta/llama-3.1-70b-instruct"
```

### Mock mode (no API key or local model required)

```dotenv
USE_MOCK_LLM=true
```

All generation, validation, and export features work in mock mode using pre-defined schema-compliant responses. Ideal for testing and demos.

### Duplicate detection thresholds

```dotenv
SEMANTIC_DUPLICATE_THRESHOLD=0.88   # cosine similarity → block
SEMANTIC_WARNING_THRESHOLD=0.80     # cosine similarity → warn
```

### Paper rules

```dotenv
DEFAULT_BLOOM_L2_PERCENT=50
DEFAULT_BLOOM_L3_PERCENT=50
DEFAULT_RATIO_TOLERANCE_PERCENT=5
MAX_PAPER_SETS=5
```

---

## Running the App

Open **two terminals**:

**Terminal 1 — Backend**

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — Frontend**

```powershell
cd frontend
npm run dev
```

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Next.js frontend |
| http://localhost:8000/api/docs | FastAPI Swagger UI |
| http://localhost:8000/api/redoc | FastAPI ReDoc |
| http://localhost:8000/api/health | Health check endpoint |

---

## Usage Workflow

```
1. Course Setup      → Enter course name, code, department, semester
2. Lesson Plan       → Upload PDF/DOCX → auto-extract chapter structure → review & confirm
3. Question Bank     → Upload XLSX/CSV → validate & import → check completeness matrix
4. Generate          → Choose exam type, sets, Bloom split → confirm blueprint → Generate
5. Faculty Review    → Review questions → Approve / Reject / Edit each → Approve Set
6. Export            → Download DOCX or PDF (approval required for final export)
```

### Page Guide

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Stats overview — question bank health, paper set counts, recent activity |
| Course Setup | `/course` | Configure course metadata and chapter structure |
| Lesson Plan | `/lesson-plan` | Upload lesson plan, view AI-extracted chapter structure |
| Question Bank | `/questions` | Import questions, browse bank, view chapter completeness |
| Generate | `/generate` | Configure and trigger paper generation |
| Faculty Review | `/review` | Review, edit, approve questions; download DOCX/PDF |
| Validation | `/validation` | Detailed validation report per paper set |
| History | `/history` | Question usage history across exam cycles |
| Settings | `/settings` | LLM health check and configuration info |

---

## Examination Patterns

### Minor / Internal Examination

| Parameter | Value |
|-----------|-------|
| Duration | 75 minutes |
| Total marks attempted | 40 |
| Questions printed | 6 sub-questions (Q1–Q3, each with (a) and (b)) |
| Choice rule | Answer any **TWO** complete questions |
| Bank source | 4 questions (66.7%) |
| AI generated | 2 questions (33.3%) |

```
Q1
  (a) ................................................................ [10 Marks]
  (b) ................................................................ [10 Marks]
Q2
  (a) ................................................................ [10 Marks]
  (b) ................................................................ [10 Marks]
Q3
  (a) ................................................................ [10 Marks]
  (b) ................................................................ [10 Marks]

Answer any TWO full questions.
```

### End-Semester Examination

| Parameter | Value |
|-----------|-------|
| Duration | 180 minutes |
| Total marks attempted | 100 |
| Questions printed | 16 sub-questions |
| Bank source | 11 questions (68.75%) |
| AI generated | 5 questions (31.25%) |

Unit structure:

| Unit | Questions | Marks | Choice |
|------|-----------|-------|--------|
| Unit 1 (Q1–Q3) | 6 sub-questions | 40 | Answer any 2 |
| Unit 2 (Q4–Q6) | 6 sub-questions | 40 | Answer any 2 |
| Unit 3 (Q7–Q8) | 4 sub-questions | 20 | Answer any 1 |

> **Note on the 70:30 rule:** "Question" means one 10-mark sub-question (e.g. Q1(a)). The ratio applies to all *printed* sub-questions, not to questions students attempt. The achieved ratios (66.7% / 68.75%) are the nearest feasible integers — this is clearly stated in the validation report.

---

## Question Bank Schema

Upload as `.xlsx`, `.csv`, or `.json`. Required columns:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `question_id` | string | ✅ | Unique, e.g. `GENAI-U1-C1-L2-Q01` |
| `unit_number` | int | ✅ | `1`, `2`, or `3` |
| `chapter_number` | int | ✅ | `1` to `7` |
| `chapter_name` | string | ✅ | Must match lesson plan |
| `question_text` | string | ✅ | Cannot be empty |
| `bloom_level` | string | ✅ | `L2` or `L3` only |
| `marks` | int | ✅ | Must be `10` |
| `model_answer` | string | ❌ | Warning generated if missing |
| `difficulty` | string | ❌ | `easy` / `medium` / `hard` |

**Target bank size:** 140 questions — 7 chapters × (10 L2 + 10 L3)

The completeness matrix on the Dashboard shows exactly which chapters are ready.

---

## Project Structure

```
Prashnopatra/
│
├── api/                          # FastAPI application
│   ├── main.py                   # App entry point, CORS, router registration
│   ├── routers/
│   │   ├── course.py             # Course info & lesson plan endpoints
│   │   ├── questions.py          # Question bank CRUD & import
│   │   ├── papers.py             # Generation, review, approval & export
│   │   ├── audit.py              # Stats & activity log
│   │   └── settings.py           # LLM health check
│   └── schemas/                  # Pydantic request/response schemas
│
├── agents/                       # Agentic workflow nodes
│   ├── coordinator.py            # Orchestrator — runs all agents in order
│   ├── intake_agent.py           # Lesson plan parsing & chapter extraction
│   ├── question_bank_agent.py    # Bank validation & normalisation
│   ├── blueprint_agent.py        # Immutable generation blueprint builder
│   ├── selection_agent.py        # Constraint-based bank question selector
│   ├── generation_agent.py       # LLM question generation
│   ├── similarity_agent.py       # Duplicate detection (exact/TF-IDF/embedding)
│   ├── composition_agent.py      # Q-slot assignment (Q1a, Q1b, …)
│   ├── valuation_agent.py        # LLM valuation scheme generation
│   ├── validation_agent.py       # Rules-based paper validation
│   └── export_agent.py           # DOCX export with approval gate
│
├── services/                     # Shared business logic
│   ├── llm_provider.py           # OpenAI-compatible LLM client (multi-provider)
│   ├── pdf_service.py            # ReportLab PDF generation
│   ├── question_bank_service.py  # File parsing & bank import
│   ├── blueprint_service.py      # Blueprint computation helpers
│   ├── similarity_service.py     # TF-IDF & embedding similarity
│   └── file_service.py           # File upload utilities
│
├── models/                       # Pydantic v2 domain models
│   ├── enums.py                  # BloomLevel, ExamType, ApprovalStatus, …
│   ├── question.py               # QuestionRecord
│   ├── blueprint.py              # MinorBlueprint, EndSemBlueprint
│   ├── paper.py                  # PaperQuestion, PaperSet, CompletePaper
│   ├── valuation.py              # ValuationScheme, ValuationPoint
│   └── validation.py             # ValidationReport, ValidationFinding
│
├── repositories/                 # SQLAlchemy data access layer
│   ├── database.py               # ORM models + init_db()
│   ├── question_repo.py          # Question CRUD
│   ├── paper_repo.py             # Paper set & question persistence
│   ├── audit_repo.py             # Audit log
│   └── settings_repo.py          # Key-value settings store
│
├── config/
│   └── settings.py               # Pydantic-settings configuration singleton
│
├── utils/
│   ├── logging_config.py         # Structured logging setup
│   ├── helpers.py                # Shared utility functions
│   └── errors.py                 # Custom exception types
│
├── frontend/                     # Next.js 16 web UI
│   └── src/
│       ├── app/
│       │   ├── page.tsx          # Dashboard
│       │   ├── course/           # Course setup
│       │   ├── lesson-plan/      # Lesson plan upload & editor
│       │   ├── questions/        # Question bank manager
│       │   ├── generate/         # Paper generation wizard
│       │   ├── review/           # Faculty review & export
│       │   ├── validation/       # Validation report viewer
│       │   ├── history/          # Usage history
│       │   └── settings/         # Settings & LLM health
│       ├── components/
│       │   ├── Sidebar.tsx       # Navigation sidebar
│       │   └── ui.tsx            # Shared UI components
│       └── lib/
│           └── api.ts            # Typed API client
│
├── tests/                        # pytest test suite
│   ├── conftest.py
│   ├── test_blueprint.py
│   ├── test_question_bank.py
│   ├── test_generation.py
│   └── test_similarity.py
│
├── data/                         # Runtime data (gitignored outputs)
│   ├── question_bank/            # Drop approved bank files here
│   ├── lesson_plan/              # Drop lesson plan files here
│   ├── university_templates/     # Drop .docx template here
│   ├── generated_outputs/
│   │   ├── drafts/               # Draft DOCX files
│   │   ├── approved/             # Final approved exports
│   │   ├── schemes/              # Valuation scheme DOCX files
│   │   └── validation_reports/   # JSON validation reports
│   └── database/
│       └── qp_agent.db           # SQLite database
│
├── app.py                        # Legacy Streamlit UI (kept, not primary)
├── .env                          # Your local config (never commit)
├── .env.example                  # Config template (safe to commit)
├── requirements.txt              # Python dependencies
└── pyproject.toml                # Project metadata
```

---

## API Reference

Base URL: `http://localhost:8000/api`

### Course

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/course/info` | Get course metadata |
| `POST` | `/course/info` | Save course metadata |
| `GET` | `/course/structure` | Get chapter structure |
| `POST` | `/course/structure` | Save chapter structure |
| `POST` | `/course/lesson-plan/extract` | Upload & extract lesson plan |

### Questions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/questions` | List questions (filter by chapter, bloom, limit) |
| `GET` | `/questions/completeness` | Chapter completeness matrix |
| `POST` | `/questions/import` | Upload & import question bank file |
| `PATCH` | `/questions/{id}` | Edit a question |
| `DELETE` | `/questions/{id}` | Delete a question |

### Papers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/papers` | List all paper sets |
| `POST` | `/papers/generate` | Trigger paper generation |
| `GET` | `/papers/{set_id}` | Get paper set with all questions |
| `PATCH` | `/papers/{set_id}/questions/{slot_id}` | Update question status/text |
| `POST` | `/papers/{set_id}/approve` | Approve a paper set |
| `GET` | `/papers/{set_id}/validation` | Get validation report |
| `GET` | `/papers/{set_id}/export/pdf` | Download paper as PDF |
| `GET` | `/papers/{set_id}/export/docx` | Download paper as DOCX |

### Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/audit/stats` | Dashboard stats |
| `GET` | `/audit/logs` | Activity log |

Full interactive docs: **http://localhost:8000/api/docs**

---

## Testing

Run the full test suite (mock LLM — no API key required):

```powershell
.\.venv\Scripts\Activate.ps1
$env:USE_MOCK_LLM = "true"
pytest tests/ -v
```

Tests cover:
- Minor and End-Sem blueprint generation
- Bank and AI question count allocation
- Bloom level distribution (50:50 and custom splits)
- Multi-set uniqueness (no cross-set bank reuse)
- Approval gating (export blocked before APPROVED status)
- Question bank validation (duplicate IDs, empty text, invalid Bloom)
- Similarity service (exact match detection)
- Database initialisation and settings loading

---

## Troubleshooting

### `Rate limit reached` on Groq
The free tier has token-per-day limits. Either wait for the reset, upgrade to the Dev Tier, or switch to `USE_MOCK_LLM=true` for testing.

### `No API key found`
Set `LLM_API_KEY` or `GROQ_API_KEY` in `.env`, or add `USE_MOCK_LLM=true`.

### `Insufficient questions for slots`
The question bank doesn't have enough L2 or L3 questions in the selected chapters. Check the completeness matrix on the Dashboard and add more questions before generating.

### Review page shows old papers after regeneration
Click the **↺ Refresh** button in the Faculty Review sidebar, or switch tabs and return — the list auto-refreshes on tab focus.

### Export returns 404
The paper set ID doesn't exist in the database. Try generating papers again.

### Sentence-transformer slow on first load
The embedding model (`all-MiniLM-L6-v2`, ~90 MB) is downloaded from HuggingFace on first use and cached locally. Subsequent starts are fast. Set `HF_TOKEN` in your environment to avoid unauthenticated rate limits.

### Frontend can't reach the backend
Make sure the backend is running on port 8000. The frontend proxies to `http://localhost:8000/api` by default. Check `NEXT_PUBLIC_API_URL` in the frontend `.env.local` if you change the port.

---

## Confidentiality Notice

⚠️ **Question papers are strictly confidential academic documents.**

- The backend binds to `127.0.0.1` only — not accessible from other machines
- Generated paper files in `data/generated_outputs/` are excluded from Git by `.gitignore`
- API keys are never logged (set `LOG_PROMPT_CONTENT=false`)
- Never commit `.env` to version control
- Never push generated paper files to any remote repository
- Reset the database (`data/database/qp_agent.db`) before production deployment

---

## Known Limitations

1. **Single course** — Only the Generative AI course (3 units, 7 chapters) is configured. Multi-course support requires a schema extension.
2. **Groq free tier** — 100k tokens/day limit. Use mock mode or a paid tier for heavy use.
3. **Embedding model download** — First run downloads ~90 MB from HuggingFace.
4. **Lesson plan extraction** — AI extraction is heuristic; always review and confirm the extracted chapter structure before generating.
5. **No authentication** — This is a local faculty tool. Add authentication before any multi-user or network deployment.

---

*Prashnopatra v0.1.0 — Generative AI Course — Question Paper Setting Agent*
