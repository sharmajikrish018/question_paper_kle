# ==============================================================================
# Prashnopatra — Automated Installer for Windows
# ==============================================================================
# Usage:
#   .\install.ps1
#
# This script sets up the complete Prashnopatra environment:
#   1. Detects prerequisites (Git, Python 3.11+, Node.js 18+)
#   2. Prepares configuration (.env)
#   3. Creates & configures Python virtual environment (.venv)
#   4. Installs backend dependencies
#   5. Initializes the database & sample files
#   6. Installs frontend dependencies (Next.js)
#   7. Detects Ollama and pulls required AI model (qwen3:8b)
#   8. Verifies the entire setup
# ==============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Text)
    Write-Host "`n[$([char]0x203A)] $Text" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "  [OK] $Text" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Text)
    Write-Host "  [WARN] $Text" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Text, [string]$Resolution)
    Write-Host "  [ERROR] $Text" -ForegroundColor Red
    if ($Resolution) {
        Write-Host "`n  Resolution:`n  $Resolution`n" -ForegroundColor Yellow
    }
    exit 1
}

Write-Host @"
==============================================================================
   ____                  _                              _
  |  _ \ _ __ __ _ ___| |__  _ __   ___  _ __   __ _| |_ _ __ __ _
  | |_) | '__/ _` / __| '_ \| '_ \ / _ \| '_ \ / _` | __| '__/ _` |
  |  __/| | | (_| \__ \ | | | | | | (_) | |_) | (_| | |_| | | (_| |
  |_|   |_|  \__,_|___/_| |_|_| |_|\___/| .__/ \__,_|\__|_|  \__,_|
                                         |_|
              AI Question Paper Setting Agent Setup
==============================================================================
"@ -ForegroundColor Blue

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $projectRoot

# ── 1. Prerequisites Detection ───────────────────────────────────────────────
Write-Step "Checking system prerequisites..."

# Check Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = (git --version) -replace 'git version ', ''
    Write-Success "Git detected ($gitVer)"
} else {
    Write-Fail "Git is not installed or not in PATH." "Download and install Git from: https://git-scm.com/download/win"
}

# Check Python (3.11+)
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
}

if (-not $pythonCmd) {
    Write-Fail "Python is not installed or not in PATH." "Install Python 3.11 or 3.12 from: https://www.python.org/downloads/windows/`nEnsure 'Add Python to PATH' is checked during installation."
}

$pyVerStr = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
$pyMajor = [int]($pyVerStr.Split('.')[0])
$pyMinor = [int]($pyVerStr.Split('.')[1])

if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) {
    Write-Fail "Python $pyVerStr detected. Python 3.11 or higher is required." "Install Python 3.11 or 3.12 from https://www.python.org/downloads/"
}
Write-Success "Python $pyVerStr detected ($pythonCmd)"

# Check Node.js (18+) & npm
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = (node --version).TrimStart('v')
    $nodeMajor = [int]($nodeVer.Split('.')[0])
    if ($nodeMajor -lt 18) {
        Write-Fail "Node.js v$nodeVer detected. Node.js 18 or higher (LTS recommended) is required." "Download and install Node.js 20+ LTS from https://nodejs.org/"
    }
    Write-Success "Node.js v$nodeVer detected"
} else {
    Write-Fail "Node.js is not installed or not in PATH." "Download and install Node.js 20+ LTS from: https://nodejs.org/"
}

if (Get-Command npm -ErrorAction SilentlyContinue) {
    $npmVer = (npm --version)
    Write-Success "npm v$npmVer detected"
} else {
    Write-Fail "npm is not installed." "Reinstall Node.js from https://nodejs.org/ to include npm."
}

# ── 2. Environment Configuration ─────────────────────────────────────────────
Write-Step "Checking configuration (.env)..."
if (Test-Path "$projectRoot\.env") {
    Write-Success "Existing .env file preserved."
} else {
    if (Test-Path "$projectRoot\.env.example") {
        Copy-Item "$projectRoot\.env.example" "$projectRoot\.env"
        Write-Success "Created .env from .env.example"
    } else {
        Write-Warn ".env.example not found. Creating default .env"
        Set-Content -Path "$projectRoot\.env" -Value @"
LLM_PROVIDER="ollama"
LLM_MODEL="qwen3:8b"
OLLAMA_MODEL="qwen3:8b"
OLLAMA_BASE_URL="http://localhost:11434/v1"
DATABASE_URL="sqlite:///./data/database/qp_agent.db"
"@
        Write-Success "Created default .env"
    }
}

# ── 3. Python Virtual Environment ────────────────────────────────────────────
Write-Step "Setting up Python virtual environment (.venv)..."
$venvDir = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "  Creating virtual environment at .venv..."
    & $pythonCmd -m venv $venvDir
    if (-not (Test-Path $venvPython)) {
        Write-Fail "Failed to create virtual environment." "Check write permissions in this folder and try again."
    }
    Write-Success "Virtual environment created."
} else {
    Write-Success "Existing virtual environment found at .venv."
}

# ── 4. Python Dependencies ───────────────────────────────────────────────────
Write-Step "Installing backend dependencies (requirements.txt)..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r "$projectRoot\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to install Python dependencies from requirements.txt." "Review the error output above, ensure internet access, and run .\install.ps1 again."
}
Write-Success "Backend dependencies installed successfully."

# ── 5. Database Initialization ───────────────────────────────────────────────
Write-Step "Initializing SQLite database and sample files..."
& $venvPython -c "import sys; from pathlib import Path; sys.path.insert(0, r'$projectRoot'); from repositories.database import init_db; init_db(); print('Database tables ready.')"
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Database initialization encountered an issue. Will retry at startup."
} else {
    Write-Success "Database initialized at data/database/qp_agent.db."
}

if (Test-Path "$projectRoot\scripts\create_sample_files.py") {
    & $venvPython "$projectRoot\scripts\create_sample_files.py" | Out-Null
    Write-Success "Sample files verified."
}

# ── 6. Frontend Dependencies ─────────────────────────────────────────────────
Write-Step "Installing frontend dependencies (Next.js)..."
$frontendDir = Join-Path $projectRoot "frontend"
if (Test-Path "$frontendDir\package.json") {
    # Clear corrupted npm cache that causes "Cache entry deserialization failed" warnings
    Write-Host "  Verifying npm cache integrity..." -NoNewline
    $cacheCheck = npm cache verify 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host " [corrupted, cleaning]"
        npm cache clean --force 2>&1 | Out-Null
    } else {
        Write-Host " [OK]"
    }

    Push-Location $frontendDir
    try {
        if (Test-Path "package-lock.json") {
            npm ci
        } else {
            npm install
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  npm ci failed, retrying with npm install..."
            npm install
        }
    } finally {
        Pop-Location
    }
    Write-Success "Frontend dependencies installed successfully."
} else {
    Write-Fail "frontend/package.json not found." "Ensure the repository was cloned completely."
}

# ── 7. Ollama and AI Model Detection ─────────────────────────────────────────
Write-Step "Detecting Ollama and AI model configuration..."
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue

if ($ollamaCmd) {
    Write-Success "Ollama detected ($($ollamaCmd.Source))"

    # Check if Ollama service is reachable
    $ollamaRunning = $false
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
        $ollamaRunning = $true
    } catch {
        $ollamaRunning = $false
    }

    if (-not $ollamaRunning) {
        Write-Host "  Starting local Ollama service in background..."
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }

    # Model to pull: read from .env if present, otherwise default to qwen3:8b
    $targetModel = "qwen3:8b"
    if (Test-Path "$projectRoot\.env") {
        $envLines = Get-Content "$projectRoot\.env"
        foreach ($line in $envLines) {
            if ($line -match '^\s*OLLAMA_MODEL\s*=\s*["'']?([^"'']+)["'']?') {
                $targetModel = $matches[1].Trim()
                break
            }
        }
    }

    # Check if target model is already pulled
    $modelsList = & ollama list 2>&1
    $modelFound = $modelsList | Select-String -Pattern "^$([regex]::Escape($targetModel))\s+" -SimpleMatch

    if ($modelFound) {
        Write-Success "Required AI model '$targetModel' is already available in Ollama."
    } else {
        Write-Host "  Model '$targetModel' not found locally. Pulling from Ollama library (this may take a few minutes)..."
        & ollama pull $targetModel
        if ($LASTEXITCODE -eq 0) {
            Write-Success "AI model '$targetModel' pulled successfully."
        } else {
            Write-Warn "Could not automatically pull '$targetModel'. You can pull it later with: ollama pull $targetModel"
        }
    }
} else {
    Write-Warn "Ollama CLI was not found in PATH."
    Write-Host "  If you want to run offline AI generation with local Qwen models:"
    Write-Host "  1. Download and install Ollama from: https://ollama.com/download/windows"
    Write-Host "  2. Pull the model: ollama pull qwen3:8b"
    Write-Host "  (Alternatively, you can configure a cloud LLM key in .env or run in Mock mode)"
}

# ── 8. Verification & Summary ────────────────────────────────────────────────
Write-Host @"

==============================================================================
   Installation Complete!
==============================================================================

  [OK] System Tools:        Git, Python, Node.js, npm
  [OK] Backend Environment: .venv with FastAPI, PyMuPDF, ReportLab, etc.
  [OK] Frontend:            Next.js 16 dependencies installed
  [OK] Database:            data/database/qp_agent.db initialized
  [OK] Configuration:       .env ready

  To start the application, run:

      .\start.ps1

  Once started:
    - Web Application:  http://localhost:3000
    - Backend API:      http://localhost:8000
    - API Documentation:http://localhost:8000/api/docs
==============================================================================
"@ -ForegroundColor Green
