#!/usr/bin/env bash
# =============================================================================
#  1-Click Automated Deployment Script (Linux / macOS / Cloud EC2)
# =============================================================================
set -e

echo "============================================================"
echo "  🚀 AI Resume Screening & Matching System - Auto Deploy"
echo "============================================================"

MODE="${1:-dev}"

if [ "$MODE" = "docker" ]; then
    echo "[1/1] Starting Docker multi-container stack..."
    docker compose up --build
    exit 0
fi

if [ "$MODE" = "benchmark" ]; then
    echo "[1/1] Running Concurrency & Latency Benchmark..."
    cd backend
    python3 benchmark_concurrency.py
    exit 0
fi

if [ "$MODE" = "test" ]; then
    echo "[1/1] Running Pytest Suite..."
    cd backend
    pytest tests/ -v
    exit 0
fi

echo "[1/3] Setting up Python backend..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pytest tests/ -v --tb=short

echo "[2/3] Setting up Frontend..."
cd ../frontend
npm install --silent
npm run build

echo "[3/3] System is verified and ready!"
echo "Run 'docker compose up --build' or launch backend and frontend servers."
