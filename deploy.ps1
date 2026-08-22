# =============================================================================
#  1-Click Automated Deployment Script (Windows PowerShell)
# =============================================================================
param (
    [switch]$Docker,
    [switch]$TestOnly,
    [switch]$Benchmark
)

$ErrorActionPreference = "Stop"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  🚀 AI Resume Screening & Matching System - Auto Deploy" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$WorkspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Docker Compose Mode
if ($Docker) {
    Write-Host "[1/1] Launching multi-container stack via Docker Compose..." -ForegroundColor Green
    docker compose up --build
    exit 0
}

# 2. Run Benchmarks
if ($Benchmark) {
    Write-Host "[1/1] Executing High-Throughput Concurrency Benchmark..." -ForegroundColor Yellow
    Set-Location "$WorkspaceRoot\backend"
    & .\venv\Scripts\python.exe benchmark_concurrency.py
    exit 0
}

# 3. Backend Setup & Verification
Write-Host "`n[1/3] Setting up Python Backend..." -ForegroundColor Yellow
Set-Location "$WorkspaceRoot\backend"

if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Gray
    python -m venv venv
}

& .\venv\Scripts\pip.exe install -r requirements.txt --quiet
Write-Host "Running automated Pytest verification suite..." -ForegroundColor Gray
& .\venv\Scripts\pytest.exe tests/ -v --tb=short

if ($TestOnly) {
    Write-Host "Test suite passed! Exiting as requested." -ForegroundColor Green
    exit 0
}

# 4. Frontend Setup & Build Validation
Write-Host "`n[2/3] Setting up React Frontend..." -ForegroundColor Yellow
Set-Location "$WorkspaceRoot\frontend"
npm install --silent
npm run build

# 5. Launch Local Dev Services
Write-Host "`n[3/3] Starting Services..." -ForegroundColor Green
Write-Host "  - Backend API: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "  - Swagger Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  - Frontend Portal: http://localhost:5173" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to terminate.`n" -ForegroundColor Gray

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\backend'; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\frontend'; npm run dev"
