# Developer shortcuts (Linux/macOS/WSL; on Windows use deploy.ps1). Run `make help` for the list.
# Each target only wraps the commands documented in README.md, so nothing here is required.
PY ?= python

.PHONY: help install dev-backend dev-frontend test lint build benchmark docker-up docker-down clean

help:
	@echo "install       Install backend (incl. test tools) and frontend dependencies"
	@echo "dev-backend   Run the API with auto-reload on http://127.0.0.1:8000"
	@echo "dev-frontend  Run the React dev server on http://localhost:5173"
	@echo "test          Run the backend test suite"
	@echo "lint          Lint backend (ruff) and frontend (eslint)"
	@echo "build         Build the production frontend bundle"
	@echo "benchmark     Micro-benchmark the scoring function"
	@echo "docker-up     Build and start the full stack with Docker Compose"
	@echo "docker-down   Stop the stack (data volumes are kept)"

install:
	cd backend && $(PY) -m pip install -r requirements-dev.txt
	cd frontend && npm ci

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && $(PY) -m pytest -q

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

build:
	cd frontend && npm run build

benchmark:
	cd backend && $(PY) benchmark_scoring.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache frontend/dist
