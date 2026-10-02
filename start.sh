#!/usr/bin/env bash
# ==============================================================================
# Prashnopatra — Automated Startup Script for macOS & Linux
# ==============================================================================
# Usage:
#   chmod +x ./start.sh
#   ./start.sh             # Start backend & frontend services
#   ./start.sh --restart   # Restart all services
#   ./start.sh --stop      # Stop any running services
#   ./start.sh --headless  # Start without opening the browser
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

get_port_pid() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti :"$port" 2>/dev/null | head -n 1
    elif command -v fuser >/dev/null 2>&1; then
        fuser "$port"/tcp 2>/dev/null | awk '{print $1}'
    fi
}

stop_port_process() {
    local port=$1
    local name=$2
    local pid
    pid=$(get_port_pid "$port")
    if [ -n "$pid" ] && [ "$pid" -gt 1 ]; then
        echo -e "  ${YELLOW}Stopping $name on port $port (PID: $pid)...${NC}"
        kill -9 "$pid" 2>/dev/null || true
        sleep 0.5
    fi
}

RESTART=false
STOP=false
HEADLESS=false

for arg in "$@"; do
    case "$arg" in
        --restart) RESTART=true ;;
        --stop)    STOP=true ;;
        --headless) HEADLESS=true ;;
    esac
done

echo -e "${BLUE}"
cat << "EOF"
==============================================================================
   ____                  _                              _
  |  _ \ _ __ __ _ ___| |__  _ __   ___  _ __   __ _| |_ _ __ __ _
  | |_) | '__/ _` / __| '_ \| '_ \ / _ \| '_ \ / _` | __| '__/ _` |
  |  __/| | | (_| \__ \ | | | | | | (_) | |_) | (_| | |_| | | (_| |
  |_|   |_|  \__,_|___/_| |_|_| |_|\___/| .__/ \__,_|\__|_|  \__,_|
                                         |_|
              AI Question Paper Setting Agent Startup
==============================================================================
EOF
echo -e "${NC}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

mkdir -p "$PROJECT_ROOT/logs"

# ── Handle --stop ─────────────────────────────────────────────────────────────
if [ "$STOP" = true ]; then
    write_step "Stopping Prashnopatra services..."
    stop_port_process 8000 "Backend API"
    stop_port_process 3000 "Frontend UI"
    write_success "All services stopped."
    exit 0
fi

# ── 1. Check Prerequisites ───────────────────────────────────────────────────
write_step "Checking installation..."

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    write_fail "Python virtual environment not found (.venv)." "Run the installer first:\n    ./install.sh"
fi

FRONTEND_DIR="$PROJECT_ROOT/frontend"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    write_fail "Frontend dependencies not found (frontend/node_modules)." "Run the installer first:\n    ./install.sh"
fi
write_success "Virtual environment and frontend dependencies verified."

# ── 2. Check Ollama Service ──────────────────────────────────────────────────
write_step "Checking AI service (Ollama)..."
OLLAMA_RUNNING=false
if curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    OLLAMA_RUNNING=true
fi

if [ "$OLLAMA_RUNNING" = false ]; then
    if command -v ollama >/dev/null 2>&1; then
        echo -e "  Starting local Ollama service in background..."
        ollama serve >/dev/null 2>&1 &
        sleep 2
        if curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            write_success "Ollama service started."
        else
            write_warn "Ollama could not be verified automatically. Proceeding anyway."
        fi
    else
        write_warn "Ollama is not installed or not running. Local AI paper generation will be offline unless cloud LLM key is configured in .env."
    fi
else
    write_success "Ollama service is active (http://localhost:11434)."
fi

# ── 3. Check for Port Conflicts & Handle --restart ────────────────────────────
write_step "Checking port availability..."

if [ "$RESTART" = true ]; then
    echo -e "  ${YELLOW}Restart flag detected. Stopping any existing instances...${NC}"
    stop_port_process 8000 "Backend API"
    stop_port_process 3000 "Frontend UI"
fi

BACKEND_PID=$(get_port_pid 8000)
FRONTEND_PID=$(get_port_pid 3000)

BACKEND_HEALTHY=false
if [ -n "$BACKEND_PID" ]; then
    if curl -s -m 2 http://127.0.0.1:8000/api/health | grep -q '"ok"'; then
        BACKEND_HEALTHY=true
        write_success "Backend API is already running on port 8000 (PID: $BACKEND_PID)."
    fi
fi

FRONTEND_HEALTHY=false
if [ -n "$FRONTEND_PID" ]; then
    if curl -s -m 2 http://127.0.0.1:3000 >/dev/null 2>&1; then
        FRONTEND_HEALTHY=true
        write_success "Frontend UI is already running on port 3000 (PID: $FRONTEND_PID)."
    fi
fi

# If both are already running and healthy, print status and exit
if [ "$BACKEND_HEALTHY" = true ] && [ "$FRONTEND_HEALTHY" = true ] && [ "$RESTART" = false ]; then
    echo -e "${GREEN}"
    cat << EOF

==============================================================================
   Prashnopatra is already running!
==============================================================================

  [OK] Web Application:    http://localhost:3000
  [OK] Backend API:        http://localhost:8000
  [OK] API Documentation:  http://localhost:8000/api/docs
  [OK] Ollama Service:     http://localhost:11434

Commands:
  - To restart services:   ./start.sh --restart
  - To stop services:      ./start.sh --stop
==============================================================================
EOF
    echo -e "${NC}"
    if [ "$HEADLESS" = false ]; then
        if command -v open >/dev/null 2>&1; then
            open "http://localhost:3000"
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "http://localhost:3000"
        fi
    fi
    exit 0
fi

# ── 4. Launch Backend API ────────────────────────────────────────────────────
SPAWNED_BACKEND_PID=""
if [ "$BACKEND_HEALTHY" = false ]; then
    if [ -n "$BACKEND_PID" ]; then
        write_warn "Port 8000 is occupied by an unresponsive process (PID: $BACKEND_PID). Terminating..."
        stop_port_process 8000 "Unresponsive backend"
    fi
    write_step "Starting backend API (FastAPI / Uvicorn)..."
    "$VENV_PYTHON" -m uvicorn api.main:app --port 8000 > "$PROJECT_ROOT/logs/backend.log" 2> "$PROJECT_ROOT/logs/backend_error.log" &
    SPAWNED_BACKEND_PID=$!

    echo -n "  Waiting for backend API to initialize..."
    READY=false
    for _ in {1..25}; do
        sleep 0.8
        echo -n "."
        if curl -s -m 2 http://127.0.0.1:8000/api/health | grep -q '"ok"'; then
            READY=true
            break
        fi
    done
    echo ""
    if [ "$READY" = true ]; then
        write_success "Backend API ready at http://localhost:8000 (PID: $SPAWNED_BACKEND_PID)"
    else
        write_fail "Backend API failed to start." "Check logs at: $PROJECT_ROOT/logs/backend_error.log"
    fi
fi

# ── 5. Launch Frontend UI ────────────────────────────────────────────────────
SPAWNED_FRONTEND_PID=""
if [ "$FRONTEND_HEALTHY" = false ]; then
    if [ -n "$FRONTEND_PID" ]; then
        write_warn "Port 3000 is occupied by an unresponsive process (PID: $FRONTEND_PID). Terminating..."
        stop_port_process 3000 "Unresponsive frontend"
    fi
    write_step "Starting frontend UI (Next.js)..."
    (cd "$FRONTEND_DIR" && npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2> "$PROJECT_ROOT/logs/frontend_error.log") &
    SPAWNED_FRONTEND_PID=$!

    echo -n "  Waiting for frontend UI to initialize..."
    READY=false
    for _ in {1..30}; do
        sleep 1
        echo -n "."
        if curl -s -m 2 http://127.0.0.1:3000 >/dev/null 2>&1; then
            READY=true
            break
        fi
    done
    echo ""
    if [ "$READY" = true ]; then
        write_success "Frontend UI ready at http://localhost:3000"
    else
        write_fail "Frontend UI failed to start." "Check logs at: $PROJECT_ROOT/logs/frontend_error.log"
    fi
fi

# ── 6. Cleanup Handler & Process Monitor ─────────────────────────────────────
cleanup() {
    echo -e "\n${CYAN}Stopping services...${NC}"
    if [ -n "$SPAWNED_BACKEND_PID" ]; then
        kill "$SPAWNED_BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$SPAWNED_FRONTEND_PID" ]; then
        kill "$SPAWNED_FRONTEND_PID" 2>/dev/null || true
    fi
    stop_port_process 8000 "Backend API"
    stop_port_process 3000 "Frontend UI"
    echo -e "  ${GREEN}[OK]${NC} All services stopped cleanly."
    exit 0
}

trap cleanup INT TERM EXIT

echo -e "${GREEN}"
cat << EOF

==============================================================================
   Prashnopatra is running!
==============================================================================

  [OK] Web Application:    http://localhost:3000
  [OK] Backend API:        http://localhost:8000
  [OK] API Documentation:  http://localhost:8000/api/docs
  [OK] Ollama Service:     http://localhost:11434

  Logs:
    - Backend:  $PROJECT_ROOT/logs/backend.log
    - Frontend: $PROJECT_ROOT/logs/frontend.log

  Press Ctrl+C to stop all services...
==============================================================================
EOF
echo -e "${NC}"

if [ "$HEADLESS" = false ]; then
    if command -v open >/dev/null 2>&1; then
        open "http://localhost:3000" 2>/dev/null || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:3000" 2>/dev/null || true
    fi
fi

# Wait for background processes or user interrupt
while true; do
    sleep 1
    if [ -n "$SPAWNED_BACKEND_PID" ] && ! kill -0 "$SPAWNED_BACKEND_PID" 2>/dev/null; then
        write_warn "Backend API process exited unexpectedly."
        break
    fi
    if [ -n "$SPAWNED_FRONTEND_PID" ] && ! kill -0 "$SPAWNED_FRONTEND_PID" 2>/dev/null; then
        write_warn "Frontend UI process exited unexpectedly."
        break
    fi
done
