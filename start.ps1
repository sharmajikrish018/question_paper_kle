# ==============================================================================
# Prashnopatra — Automated Startup Script for Windows
# ==============================================================================
# Usage:
#   .\start.ps1             # Start backend & frontend services
#   .\start.ps1 -Restart    # Restart all services
#   .\start.ps1 -Stop       # Stop any running services
#   .\start.ps1 -Headless   # Start without opening the browser
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$Restart,
    [switch]$Stop,
    [switch]$Headless
)

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

function Get-PortPID {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($conn) { return $conn.OwningProcess }
    } catch {}
    return $null
}

function Stop-PortProcess {
    param([int]$Port, [string]$ServiceName)
    $pidToKill = Get-PortPID -Port $Port
    if ($pidToKill -and $pidToKill -gt 4) {
        Write-Host "  Stopping $ServiceName on port $Port (PID: $pidToKill)..." -ForegroundColor Yellow
        try {
            Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        } catch {}
    }
}

Write-Host @"
==============================================================================
   ____                  _                              _
  |  _ \ _ __ __ _ ___| |__  _ __   ___  _ __   __ _| |_ _ __ __ _
  | |_) | '__/ _` / __| '_ \| '_ \ / _ \| '_ \ / _` | __| '__/ _` |
  |  __/| | | (_| \__ \ | | | | | | (_) | |_) | (_| | |_| | | (_| |
  |_|   |_|  \__,_|___/_| |_|_| |_|\___/| .__/ \__,_|\__|_|  \__,_|
                                         |_|
              AI Question Paper Setting Agent Startup
==============================================================================
"@ -ForegroundColor Blue

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $projectRoot

# Ensure logs directory exists
if (-not (Test-Path "$projectRoot\logs")) {
    New-Item -ItemType Directory -Path "$projectRoot\logs" -Force | Out-Null
}

# ── Handle -Stop Switch ───────────────────────────────────────────────────────
if ($Stop) {
    Write-Step "Stopping Prashnopatra services..."
    Stop-PortProcess -Port 8000 -ServiceName "Backend API"
    Stop-PortProcess -Port 3000 -ServiceName "Frontend UI"
    Write-Success "All services stopped."
    exit 0
}

# ── 1. Check Prerequisites ───────────────────────────────────────────────────
Write-Step "Checking installation..."

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Fail "Python virtual environment not found (.venv)." "Run the installer first:`n    .\install.ps1"
}

$frontendDir = Join-Path $projectRoot "frontend"
$nodeModulesDir = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModulesDir)) {
    Write-Fail "Frontend dependencies not found (frontend/node_modules)." "Run the installer first:`n    .\install.ps1"
}

Write-Success "Virtual environment and frontend dependencies verified."

# ── 2. Check Ollama Service ──────────────────────────────────────────────────
Write-Step "Checking AI service (Ollama)..."
$ollamaRunning = $false
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
    $ollamaRunning = $true
} catch {
    $ollamaRunning = $false
}

if (-not $ollamaRunning) {
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Host "  Starting local Ollama service in background..."
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
            $ollamaRunning = $true
            Write-Success "Ollama service started."
        } catch {
            Write-Warn "Ollama could not be verified automatically. Proceeding anyway."
        }
    } else {
        Write-Warn "Ollama is not installed or not running. Local AI paper generation will be offline unless cloud LLM key is configured in .env."
    }
} else {
    Write-Success "Ollama service is active (http://localhost:11434)."
}

# ── 3. Check for Port Conflicts & Handle -Restart ──────────────────────────────
Write-Step "Checking port availability..."

if ($Restart) {
    Write-Host "  Restart flag detected. Stopping any existing instances..." -ForegroundColor Yellow
    Stop-PortProcess -Port 8000 -ServiceName "Backend API"
    Stop-PortProcess -Port 3000 -ServiceName "Frontend UI"
}

$backendPID = Get-PortPID -Port 8000
$frontendPID = Get-PortPID -Port 3000

$backendHealthy = $false
if ($backendPID) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($health.status -eq "ok") {
            $backendHealthy = $true
            Write-Success "Backend API is already running on port 8000 (PID: $backendPID)."
        }
    } catch {}
}

$frontendHealthy = $false
if ($frontendPID) {
    try {
        $fe = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($fe.StatusCode -eq 200) {
            $frontendHealthy = $true
            Write-Success "Frontend UI is already running on port 3000 (PID: $frontendPID)."
        }
    } catch {}
}

# If both are already running and healthy, print status and exit
if ($backendHealthy -and $frontendHealthy -and -not $Restart) {
    Write-Host @"

==============================================================================
   Prashnopatra is already running!
==============================================================================

  [OK] Web Application:    http://localhost:3000
  [OK] Backend API:        http://localhost:8000
  [OK] API Documentation:  http://localhost:8000/api/docs
  [OK] Ollama Service:     http://localhost:11434

Commands:
  - To restart services:   .\start.ps1 -Restart
  - To stop services:      .\start.ps1 -Stop
==============================================================================
"@ -ForegroundColor Green
    if (-not $Headless) {
        Start-Process "http://localhost:3000"
    }
    exit 0
}

# ── 4. Launch Backend API ────────────────────────────────────────────────────
$backendProc = $null
if (-not $backendHealthy) {
    if ($backendPID) {
        Write-Warn "Port 8000 is occupied by an unresponsive process (PID: $backendPID). Terminating..."
        Stop-PortProcess -Port 8000 -ServiceName "Unresponsive backend"
    }
    Write-Step "Starting backend API (FastAPI / Uvicorn)..."
    $backendProc = Start-Process `
        -FilePath $venvPython `
        -ArgumentList "-m uvicorn api.main:app --port 8000" `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$projectRoot\logs\backend.log" `
        -RedirectStandardError "$projectRoot\logs\backend_error.log" `
        -PassThru

    Write-Host "  Waiting for backend API to initialize..." -NoNewline
    $ready = $false
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 800
        Write-Host "." -NoNewline
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($health.status -eq "ok") {
                $ready = $true
                break
            }
        } catch {}
    }
    Write-Host ""
    if ($ready) {
        Write-Success "Backend API ready at http://localhost:8000 (PID: $($backendProc.Id))"
    } else {
        Write-Fail "Backend API failed to start." "Check logs at: $projectRoot\logs\backend_error.log"
    }
}

# ── 5. Launch Frontend UI ────────────────────────────────────────────────────
$frontendProc = $null
if (-not $frontendHealthy) {
    if ($frontendPID) {
        Write-Warn "Port 3000 is occupied by an unresponsive process (PID: $frontendPID). Terminating..."
        Stop-PortProcess -Port 3000 -ServiceName "Unresponsive frontend"
    }
    Write-Step "Starting frontend UI (Next.js)..."
    # Resolve npm.cmd explicitly — Start-Process cannot launch .ps1 scripts directly
    # Get-Command npm may return npm.ps1 which causes "not a valid Win32 application"
    $npmCmd = $null
    $npmResolved = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if ($npmResolved) {
        # Try sibling npm.cmd in the same directory
        $npmCmdCandidate = Join-Path (Split-Path $npmResolved) "npm.cmd"
        if (Test-Path $npmCmdCandidate) {
            $npmCmd = $npmCmdCandidate
        }
    }
    if (-not $npmCmd) {
        # Search every PATH entry for npm.cmd
        foreach ($dir in ($env:PATH -split ';')) {
            $candidate = Join-Path $dir "npm.cmd"
            if (Test-Path $candidate) { $npmCmd = $candidate; break }
        }
    }
    if (-not $npmCmd) { $npmCmd = "npm.cmd" }   # last-resort fallback

    $frontendProc = Start-Process `
        -FilePath $npmCmd `
        -ArgumentList "run dev" `
        -WorkingDirectory $frontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$projectRoot\logs\frontend.log" `
        -RedirectStandardError "$projectRoot\logs\frontend_error.log" `
        -PassThru

    Write-Host "  Waiting for frontend UI to initialize..." -NoNewline
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 1000
        Write-Host "." -NoNewline
        try {
            $fe = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($fe.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {}
    }
    Write-Host ""
    if ($ready) {
        Write-Success "Frontend UI ready at http://localhost:3000"
    } else {
        Write-Fail "Frontend UI failed to start." "Check logs at: $projectRoot\logs\frontend_error.log"
    }
}

# ── 6. Display Status & Monitor ──────────────────────────────────────────────
Write-Host @"

==============================================================================
   Prashnopatra is running!
==============================================================================

  [OK] Web Application:    http://localhost:3000
  [OK] Backend API:        http://localhost:8000
  [OK] API Documentation:  http://localhost:8000/api/docs
  [OK] Ollama Service:     http://localhost:11434

  Logs:
    - Backend:  $projectRoot\logs\backend.log
    - Frontend: $projectRoot\logs\frontend.log

  Press Ctrl+C to stop all services...
==============================================================================
"@ -ForegroundColor Green

if (-not $Headless) {
    Start-Process "http://localhost:3000"
}

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backendProc -and $backendProc.HasExited) {
            Write-Warn "Backend API terminated unexpectedly with exit code $($backendProc.ExitCode)."
            break
        }
        if ($frontendProc -and $frontendProc.HasExited) {
            Write-Warn "Frontend UI terminated unexpectedly with exit code $($frontendProc.ExitCode)."
            break
        }
    }
} finally {
    Write-Host "`nStopping services..." -ForegroundColor Cyan
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    Stop-PortProcess -Port 8000 -ServiceName "Backend API"
    Stop-PortProcess -Port 3000 -ServiceName "Frontend UI"
    Write-Success "All services stopped cleanly."
}
