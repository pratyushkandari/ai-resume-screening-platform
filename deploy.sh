#!/usr/bin/env bash
# Set up and verify the project on Linux/macOS.
#   ./deploy.sh            install dependencies, run tests, build the frontend
#   ./deploy.sh docker     build and start the Docker Compose stack
#   ./deploy.sh test       run the backend tests only
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:-setup}"

case "$MODE" in
  docker)
    [ -f .env ] || { echo "Create .env from .env.example first (JWT_SECRET_KEY, POSTGRES_PASSWORD)."; exit 1; }
    docker compose up --build
    ;;
  test)
    # Use the project virtualenv created by "setup" when it exists.
    (cd backend && { [ -f .venv/bin/activate ] && . .venv/bin/activate; true; } && python3 -m pytest -q)
    ;;
  setup)
    echo "[1/3] Backend dependencies"
    (cd backend && { [ -d .venv ] || python3 -m venv .venv; } && . .venv/bin/activate \
      && pip install --quiet --upgrade pip && pip install --quiet -r requirements-dev.txt \
      && echo "[2/3] Backend tests" && python -m pytest -q)
    echo "[3/3] Frontend build"
    (cd frontend && npm ci --no-audit --no-fund && npm run build)
    echo "Done. Start the API:  cd backend && . .venv/bin/activate && uvicorn app.main:app --reload"
    echo "Start the UI:   cd frontend && npm run dev   (http://localhost:5173)"
    ;;
  *)
    echo "Usage: $0 [setup|test|docker]"; exit 1 ;;
esac
