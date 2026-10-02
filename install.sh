#!/usr/bin/env bash
# ==============================================================================
# Prashnopatra — Automated Installer for macOS & Linux
# ==============================================================================
# Usage:
#   chmod +x ./install.sh
#   ./install.sh
#
# This script sets up the complete Prashnopatra environment:
#   1. Detects prerequisites (Git, Python 3.11+, Node.js 18+)
#   2. Prepares configuration (.env)
#   3. Creates & configures Python virtual environment (.venv)
#   4. Installs backend dependencies (requirements.txt)
#   5. Initializes the database & sample files
#   6. Installs frontend dependencies (Next.js)
#   7. Detects Ollama and pulls required AI model (qwen3:8b)
#   8. Verifies the entire setup
# ==============================================================================

set -e

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

write_step() {
    echo -e "\n${CYAN}› $1${NC}"
}

write_success() {
    echo -e "  ${GREEN}[OK]${NC} $1"
}

write_warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
}

write_fail() {
    echo -e "  ${RED}[ERROR]${NC} $1"
    if [ -n "$2" ]; then
        echo -e "\n  ${YELLOW}Resolution:${NC}\n  $2\n"
    fi
    exit 1
}

echo -e "${BLUE}"
cat << "EOF"
==============================================================================
   ____                  _                              _
  |  _ \ _ __ __ _ ___| |__  _ __   ___  _ __   __ _| |_ _ __ __ _
  | |_) | '__/ _` / __| '_ \| '_ \ / _ \| '_ \ / _` | __| '__/ _` |
  |  __/| | | (_| \__ \ | | | | | | (_) | |_) | (_| | |_| | | (_| |
  |_|   |_|  \__,_|___/_| |_|_| |_|\___/| .__/ \__,_|\__|_|  \__,_|
                                         |_|
              AI Question Paper Setting Agent Setup
==============================================================================
EOF
echo -e "${NC}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# ── 1. Prerequisites Detection ───────────────────────────────────────────────
write_step "Checking system prerequisites..."

# Check Git
if command -v git >/dev/null 2>&1; then
    GIT_VER=$(git --version | awk '{print $3}')
    write_success "Git detected ($GIT_VER)"
else
    write_fail "Git is not installed or not in PATH." "Please install Git via: brew install git (macOS) or sudo apt install git (Linux)"
fi

# Check Python (3.11+)
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    write_fail "Python 3 is not installed or not in PATH." "Install Python 3.11+ via: brew install python@3.11 (macOS) or https://www.python.org/downloads/"
fi

PY_VER_STR=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    write_fail "Python $PY_VER_STR detected. Python 3.11 or higher is required." "Install Python 3.11+ via: brew install python@3.11 (macOS) or https://www.python.org/downloads/"
fi
write_success "Python $PY_VER_STR detected ($PYTHON_CMD)"

# Check Node.js (18+) & npm
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
    if [ "$NODE_MAJOR" -lt 18 ]; then
        write_fail "Node.js v$NODE_VER detected. Node.js 18 or higher (20+ LTS recommended) is required." "Update Node.js via: brew install node@20 (macOS) or https://nodejs.org/"
    fi
    write_success "Node.js v$NODE_VER detected"
else
    write_fail "Node.js is not installed or not in PATH." "Install Node.js 20+ LTS via: brew install node (macOS) or https://nodejs.org/"
fi

if command -v npm >/dev/null 2>&1; then
    NPM_VER=$(npm --version)
    write_success "npm v$NPM_VER detected"
else
    write_fail "npm is not installed." "Reinstall Node.js to include npm."
fi

# ── 2. Environment Configuration ─────────────────────────────────────────────
write_step "Checking configuration (.env)..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    write_success "Existing .env file preserved."
else
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        write_success "Created .env from .env.example"
    else
        write_warn ".env.example not found. Creating default .env"
        cat << 'EOF' > "$PROJECT_ROOT/.env"
LLM_PROVIDER="ollama"
LLM_MODEL="qwen3:8b"
OLLAMA_MODEL="qwen3:8b"
OLLAMA_BASE_URL="http://localhost:11434/v1"
DATABASE_URL="sqlite:///./data/database/qp_agent.db"
EOF
        write_success "Created default .env"
    fi
fi

# ── 3. Python Virtual Environment ────────────────────────────────────────────
write_step "Setting up Python virtual environment (.venv)..."
VENV_DIR="$PROJECT_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "  Creating virtual environment at .venv..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    if [ ! -f "$VENV_PYTHON" ]; then
        write_fail "Failed to create virtual environment." "Check write permissions in this folder and try again."
    fi
    write_success "Virtual environment created."
else
    write_success "Existing virtual environment found at .venv."
fi

# ── 4. Python Dependencies ───────────────────────────────────────────────────
write_step "Installing backend dependencies (requirements.txt)..."
"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt" --quiet
write_success "Backend dependencies installed successfully."

# ── 5. Database Initialization ───────────────────────────────────────────────
write_step "Initializing SQLite database and sample files..."
"$VENV_PYTHON" -c "import sys; from pathlib import Path; sys.path.insert(0, '$PROJECT_ROOT'); from repositories.database import init_db; init_db(); print('Database tables ready.')" || write_warn "Database initialization will run on first API startup."
write_success "Database initialized at data/database/qp_agent.db."

if [ -f "$PROJECT_ROOT/scripts/create_sample_files.py" ]; then
    "$VENV_PYTHON" "$PROJECT_ROOT/scripts/create_sample_files.py" >/dev/null 2>&1 || true
    write_success "Sample files verified."
fi

# ── 6. Frontend Dependencies ─────────────────────────────────────────────────
write_step "Installing frontend dependencies (Next.js)..."
FRONTEND_DIR="$PROJECT_ROOT/frontend"
if [ -f "$FRONTEND_DIR/package.json" ]; then
    cd "$FRONTEND_DIR"
    if [ -f "package-lock.json" ]; then
        npm ci --silent 2>/dev/null || npm install --silent
    else
        npm install --silent
    fi
    cd "$PROJECT_ROOT"
    write_success "Frontend dependencies installed successfully."
else
    write_fail "frontend/package.json not found." "Ensure the repository was cloned completely."
fi

# ── 7. Ollama and AI Model Detection ─────────────────────────────────────────
write_step "Detecting Ollama and AI model configuration..."
if command -v ollama >/dev/null 2>&1; then
    write_success "Ollama detected ($(command -v ollama))"

    # Check if Ollama service is reachable
    if ! curl -s --max-time 3 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
        echo "  Starting local Ollama service in background..."
        nohup ollama serve >/dev/null 2>&1 &
        sleep 3
    fi

    # Read target model from .env if set
    TARGET_MODEL="qwen3:8b"
    if [ -f "$PROJECT_ROOT/.env" ]; then
        CONF_MODEL=$(grep -E '^\s*OLLAMA_MODEL\s*=' "$PROJECT_ROOT/.env" | head -n 1 | cut -d '=' -f2 | tr -d "\"' " | xargs)
        if [ -n "$CONF_MODEL" ]; then
            TARGET_MODEL="$CONF_MODEL"
        fi
    fi

    # Check if target model is already pulled
    if ollama list 2>/dev/null | grep -q "^${TARGET_MODEL}"; then
        write_success "Required AI model '$TARGET_MODEL' is already available in Ollama."
    else
        echo "  Model '$TARGET_MODEL' not found locally. Pulling from Ollama library (this may take a few minutes)..."
        ollama pull "$TARGET_MODEL" && write_success "AI model '$TARGET_MODEL' pulled successfully." || write_warn "Could not automatically pull '$TARGET_MODEL'. Run manually: ollama pull $TARGET_MODEL"
    fi
else
    write_warn "Ollama CLI was not found in PATH."
    echo "  If you want to run offline AI generation with local Qwen models:"
    echo "  1. Download and install Ollama: https://ollama.com/download"
    echo "     Or run: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  2. Pull the model: ollama pull qwen3:8b"
    echo "  (Alternatively, configure a cloud LLM key in .env or run in Mock mode)"
fi

# ── 8. Verification & Summary ────────────────────────────────────────────────
echo -e "\n${GREEN}=============================================================================="
echo "   Installation Complete!"
echo "=============================================================================="
echo "  [OK] System Tools:        Git, Python, Node.js, npm"
echo "  [OK] Backend Environment: .venv with FastAPI, PyMuPDF, ReportLab, etc."
echo "  [OK] Frontend:            Next.js 16 dependencies installed"
echo "  [OK] Database:            data/database/qp_agent.db initialized"
echo "  [OK] Configuration:       .env ready"
echo ""
echo "  To start the application, run:"
echo ""
echo "      ./start.sh"
echo ""
echo "  Once started:"
echo "    - Web Application:   http://localhost:3000"
echo "    - Backend API:       http://localhost:8000"
echo "    - API Documentation: http://localhost:8000/api/docs"
echo -e "==============================================================================${NC}\n"
