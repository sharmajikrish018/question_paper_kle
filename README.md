# Prashnopatra

**Prashnopatra** is an AI-powered Question Paper Setting and Validation Agent designed for university faculty. It automates syllabus-grounded question paper creation by combining approved questions from institutional question banks (~70%) with curriculum-aligned LLM generation (~30%). The system enforces Bloom's taxonomy distributions, parses lesson plan marking schemes, runs automated 10-rule institutional compliance validation, and guarantees complete academic integrity through a human-in-the-loop Faculty Review gate before final DOCX and PDF export.

---

## Quick Start

### Windows

```powershell
.\install.ps1
```

After installation finishes:

```powershell
.\start.ps1
```

### macOS & Linux

```bash
chmod +x ./install.sh ./start.sh
./install.sh
```

After installation finishes:

```bash
./start.sh
```

> The commands above are the **only** commands required to set up and run Prashnopatra. All dependencies, virtual environments, database migrations, model downloads, and services are managed automatically.

---

## System Requirements

| Prerequisite | Requirement | Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11, macOS 12+, or modern Linux | Fully tested on Windows & Linux |
| **Git** | Latest stable | Required to clone the repository |
| **Python** | **3.11** or higher (3.11 / 3.12 recommended) | Check with `python --version` |
| **Node.js** | **18.0** or higher (**20+ LTS** recommended) | Bundled with `npm` |
| **Ollama** *(Recommended)* | Latest release with `qwen3:8b` | Enables 100% local, offline AI generation |
| **Memory (RAM)** | 8 GB minimum (16 GB recommended for local LLM) | 4 GB is sufficient in Mock mode |

---

## What the Installer Does

Running `install.ps1` (Windows) or `install.sh` (macOS/Linux) automatically performs the complete environment setup:

1. **Prerequisite Verification**: Checks for Git, Python (>= 3.11), Node.js (>= 18), and npm.
2. **Configuration Setup**: Creates `.env` from `.env.example` if not already present, safely preserving any existing user settings.
3. **Backend Environment**: Creates the isolated Python virtual environment (`.venv`) and upgrades pip.
4. **Backend Dependencies**: Installs all required Python packages from `requirements.txt` (FastAPI, PyMuPDF, ReportLab, python-docx, SQLAlchemy, Pydantic, etc.).
5. **Database Initialization**: Sets up the SQLite database schema at `data/database/qp_agent.db` and generates starter sample files.
6. **Frontend Dependencies**: Installs Next.js 16 dependencies in `frontend/` using `npm`.
7. **AI Model Discovery**: Detects local Ollama installation, starts the service if needed, and downloads the default `qwen3:8b` model if not already available locally.
8. **Health Validation**: Performs a complete check to verify all components are ready for execution.

---

## Starting the Application

Start all services with a single command:

- **Windows**: `.\start.ps1`
- **macOS / Linux**: `./start.sh`

The startup script ensures Ollama is active, launches the FastAPI backend and Next.js frontend concurrently, and displays your service endpoints:

| Service | URL | Purpose |
| :--- | :--- | :--- |
| **Web Application** | [http://localhost:3000](http://localhost:3000) | Primary faculty UI |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | FastAPI REST endpoints |
| **API Documentation** | [http://localhost:8000/api/docs](http://localhost:8000/api/docs) | Interactive Swagger docs |
| **Ollama Service** | [http://localhost:11434](http://localhost:11434) | Local LLM inference server |

### Script Management Flags

- **Restart services**: `.\start.ps1 -Restart` (Windows) or `./start.sh --restart` (macOS/Linux)
- **Stop services**: `.\start.ps1 -Stop` (Windows) or `./start.sh --stop` (macOS/Linux)
- **Clean Shutdown**: Press `Ctrl+C` in the terminal to cleanly terminate both frontend and backend processes without leaving orphaned processes on ports 3000 or 8000.

---

## First-Time Usage

Follow these steps when using Prashnopatra for the first time:

1. **Launch the application** via `.\start.ps1` or `./start.sh` and open `http://localhost:3000` in your browser.
2. **Select Active Subject**: Use the dropdown in the sidebar to choose your subject or click **Course Setup** to register a new course.
3. **Configure Course Setup**: Enter Course Code, Title, Semester, and Department. Review the extracted or default examination marking schemes.
4. **Upload Question Bank**: Navigate to **Question Bank** and import questions from Excel (`.xlsx`), CSV, Word (`.docx`), or PDF.
5. **Upload Lesson Plan**: Go to **Lesson Plan** and upload your syllabus/lesson plan document. The agent extracts units, topics, and model examination patterns.
6. **Generate Question Paper**: Click **Generate Paper**, choose the exam type (ISA-I, ISA-II, or ESA), adjust Bloom taxonomy weights, and initiate generation.
7. **Faculty Review & Approval**: Review each question card, regenerate individual questions if needed, approve questions, and inspect the compliance report.
8. **View & Download**: Inspect the formatted A4 preview via **View Paper**, then export the final approved paper as DOCX or PDF.

---

## Application Workflow

```text
Select Subject ──> Course Setup ──> Question Bank ──> Lesson Plan
                                                          │
Download (DOCX/PDF) <── View Paper <── Validation <── Faculty Review <── Generate Paper
```

- **Select Subject**: All operations are scoped strictly to the currently selected subject to prevent accidental cross-course contamination.
- **Course Setup**: Stores syllabus metadata and exam configurations (total marks, full questions, sub-question splits).
- **Question Bank**: Central repository of approved departmental questions tagged with Bloom levels, Course Outcomes (COs), and difficulty.
- **Lesson Plan**: Syllabus breakdown extracted by the Intake Agent to guide generation and blueprint alignment.
- **Generate Paper**: Assembles an exam blueprint, retrieves approved bank questions, and uses the LLM to synthesize fresh questions for remaining slots.
- **Faculty Review**: Faculty oversight interface where questions can be modified, regenerated, or approved.
- **Validation**: 10-rule verification engine checking arithmetic, Bloom percentages, CO coverage, and duplicate prevention.
- **View Paper**: Realistic A4 printable layout preview matching institutional styling.
- **Download**: Exports publication-ready Word (`.docx`) and vector PDF (`.pdf`) files once all questions are approved.

---

## Subject Management

Subject scoping ensures multiple courses can be administered independently without data overlap:

- **Add Subject**: Navigate to **Course Setup** -> **Add Subject**. Specify the Course Code (e.g., `21CS61`), Course Title, Semester, and Department. All mandatory fields must be selected before saving.
- **Switch Subject**: Open the **Active Subject** selector in the sidebar. Selecting a subject dynamically loads its associated question bank, lesson plans, marking schemes, and generated papers.
- **Delete Subject**: Located within subject settings. Allows removal of a subject and its associated local configurations after user confirmation.
- **Explicit Selection Rule**: The system **does not assume or auto-select a default subject**. Faculty must explicitly choose an active subject before performing subject-specific actions.

---

## Question Paper Generation

Prashnopatra supports university examination patterns:

- **ISA-I (In-Semester Assessment 1)**: Covers initial units (typically Units 1 & 2), 30–50 marks.
- **ISA-II (In-Semester Assessment 2)**: Covers intermediate units (typically Units 3 & 4), 30–50 marks.
- **ESA (End-Semester Assessment)**: Comprehensive coverage across all units, typically 100 marks with internal choice.

### Saved Marking Scheme Consumption
During paper generation, the system retrieves the saved marking scheme directly from the database (e.g., Question 1a = 10 marks, 1b = 5 marks). **The Lesson Plan is not re-parsed during generation**, guaranteeing deterministic arithmetic, rapid generation, and exact adherence to faculty-configured question splits.

---

## Faculty Review

Faculty maintain complete control over question paper contents:

```text
Faculty Review
├── Review generated questions
├── Approve individual questions
├── Regenerate an individual question
├── Approve all questions
├── View formatted paper
├── Download DOCX
└── Download PDF
```

- **Approve Question**: Validates an individual question slot.
- **Regenerate Question**: Prompts the AI to synthesize a replacement question for that specific slot while strictly preserving the slot's original constraints (Chapter, Bloom level, CO mapping, and sub-question marks).
- **Download Lock**: Download buttons for DOCX and PDF are disabled until **100% of questions are approved** by the faculty member.

---

## Validation

The automated Validation Agent executes 10 compliance rules on every generated draft:

1. **Total Marks Compliance**: Total paper marks exactly equal the configured exam pattern.
2. **Question Structure Compliance**: Number of main questions and sub-question splits match the marking scheme.
3. **Bloom Taxonomy Distribution**: Ensures proportion of lower-order (L1–L2) vs higher-order (L3–L6) questions falls within institutional bounds.
4. **Course Outcome (CO) Coverage**: Validates that all target COs for the examination scope are addressed.
5. **Unit/Module Balance**: Ensures questions are distributed evenly across assigned chapters.
6. **Repetition & Duplicate Check**: Multi-tier similarity check (exact match, token overlap, and embeddings) ensuring similarity is below threshold (< 0.70).
7. **Difficulty Balance**: Checks distribution across Easy, Medium, and Challenging questions.
8. **Valuation Scheme Availability**: Verifies that every question includes a step-by-step marking guide.
9. **Formatting Consistency**: Ensures question titles, formulas, and sub-parts follow standardized numbering.
10. **Faculty Approval Verification**: Ensures all slots carry explicit faculty sign-off.

---

## Export / Download

- **View Paper**: An interactive, print-accurate preview modal rendering the question paper with official headers, course details, time limits, and instructions.
- **Download DOCX**: Editable Word document styled with university guidelines, standard tables, and clean indentation.
- **Download PDF**: Publication-grade vector PDF generated via ReportLab with accurate pagination and typography.
- **Valuation Guide**: Accompanying solution blueprint and step-wise mark distribution for examiners.

---

## Configuration

Prashnopatra is configured via `.env` in the project root. The installer creates this file automatically:

```ini
# LLM Provider Configuration
LLM_PROVIDER="ollama"          # Options: "ollama", "groq", "openai", "mock"
LLM_MODEL="qwen3:8b"           # Model identifier
OLLAMA_MODEL="qwen3:8b"        # Model for local Ollama instance
OLLAMA_BASE_URL="http://localhost:11434/v1"

# Database Configuration
DATABASE_URL="sqlite:///./data/database/qp_agent.db"

# Optional Cloud Acceleration
GROQ_API_KEY=""                # Free key from https://console.groq.com

# Offline Testing
USE_MOCK_LLM=false             # Set to true to test UI/workflows without LLM/GPU
```

---

## Troubleshooting

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| **Port 8000 or 3000 already in use** | A previous instance is still running in the background. | Run `.\start.ps1 -Restart` (Windows) or `./start.sh --restart` (macOS/Linux) to cleanly restart. |
| **Python not recognized** | Python is not installed or not added to your system PATH. | Install Python 3.11+ from [python.org](https://www.python.org/downloads/) and check **"Add Python to PATH"**. Then rerun `install.ps1`. |
| **Node / npm not found** | Node.js is missing or below version 18. | Download and install Node.js 20+ LTS from [nodejs.org](https://nodejs.org/) and rerun the installer. |
| **Ollama service unreachable** | Ollama is not running on port 11434. | Start Ollama manually using `ollama serve` or rerun `.\start.ps1` which attempts to launch it automatically. |
| **Model `qwen3:8b` not found** | Model was not downloaded during installation. | Run `ollama pull qwen3:8b` in your terminal or check internet connection. |
| **Download button is disabled** | One or more questions in Faculty Review are unapproved. | Review and approve all question slots in the Faculty Review page to unlock download. |

---

## Project Structure

```text
Prashnopatra/
├── install.ps1               # Automated installer for Windows
├── install.sh                # Automated installer for macOS / Linux
├── start.ps1                 # Single-command startup for Windows
├── start.sh                  # Single-command startup for macOS / Linux
├── README.md                 # Complete system documentation
├── requirements.txt          # Python backend dependencies
├── pyproject.toml            # Project configuration & metadata
├── .env.example              # Environment variables template
├── api/                      # FastAPI backend application
│   ├── main.py               # API entry point & routes
│   └── routers/              # Modular API endpoints (subjects, QP, review)
├── frontend/                 # Next.js 16 frontend application
│   ├── src/app/              # Application pages (course, bank, review, etc.)
│   ├── src/components/       # Reusable UI components
│   └── package.json          # Node.js dependencies
├── agents/                   # Agentic generation & validation workflows
├── models/                   # Pydantic data models & schemas
├── repositories/             # SQLite database layer & SQLAlchemy models
├── services/                 # Core business services (parsing, generator, export)
├── data/                     # Local storage (database, sample files, outputs)
└── logs/                     # Service runtime logs
```

---

## Important Notes

- **Academic Confidentiality**: Question papers and solution keys are restricted academic documents. Generated papers and drafts in `data/generated_outputs/` and database files in `data/database/` are strictly excluded from version control via `.gitignore`.
- **Local & Offline Privacy**: When using Ollama with `qwen3:8b`, all document parsing, question generation, and validation happen entirely on your local machine. No exam content or student data is transmitted over the internet.
- **Faculty Accountability**: Prashnopatra is an assistive productivity agent. The final authority and academic accountability always reside with the faculty reviewer.
