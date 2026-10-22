# Set up and run the project on Windows (PowerShell).
#   .\deploy.ps1            install dependencies, run tests, build, then start API + UI
#   .\deploy.ps1 -TestOnly  install and run the backend tests
#   .\deploy.ps1 -Docker    build and start the Docker Compose stack
param ([switch]$Docker, [switch]$TestOnly)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Native programs (python, npm) do not throw on failure; stop on a non-zero exit code.
function Invoke-Step([string]$Description, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit code $LASTEXITCODE)." }
}

if ($Docker) {
    if (-not (Test-Path "$Root\.env")) { throw "Create .env from .env.example first (JWT_SECRET_KEY, POSTGRES_PASSWORD)." }
    Set-Location $Root; docker compose up --build; exit $LASTEXITCODE
}

Write-Host "[1/3] Backend dependencies" -ForegroundColor Yellow
Set-Location "$Root\backend"
if (-not (Test-Path ".venv")) { Invoke-Step "Creating the virtual environment" { python -m venv .venv } }
Invoke-Step "Upgrading pip" { .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip }
Invoke-Step "Installing backend dependencies" { .\.venv\Scripts\python.exe -m pip install --quiet -r requirements-dev.txt }
Write-Host "[2/3] Backend tests" -ForegroundColor Yellow
Invoke-Step "Backend tests" { .\.venv\Scripts\python.exe -m pytest -q }
if ($TestOnly) { exit 0 }

Write-Host "[3/3] Frontend" -ForegroundColor Yellow
Set-Location "$Root\frontend"
Invoke-Step "Installing frontend dependencies" { npm ci --no-audit --no-fund }
Invoke-Step "Building the frontend" { npm run build }

Write-Host "Starting API (http://127.0.0.1:8000/docs) and UI (http://localhost:5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run dev"
