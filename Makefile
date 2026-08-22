# =============================================================================
#  Makefile - Developer Automation & Operational Commands
# =============================================================================

.PHONY: help install test build dev docker-up docker-down benchmark clean

help:
	@echo "Available commands:"
	@echo "  make install     - Install all backend and frontend dependencies"
	@echo "  make test        - Run automated Pytest suite"
	@echo "  make benchmark   - Run concurrency and latency stress benchmark"
	@echo "  make build       - Build production frontend bundle"
	@echo "  make docker-up   - Launch multi-container stack via Docker Compose"
	@echo "  make docker-down - Stop Docker Compose containers"
	@echo "  make clean       - Clean temporary cache and build artifacts"

install:
	cd backend && python -m pip install -r requirements.txt
	cd frontend && npm install

test:
	cd backend && pytest tests/ -v

benchmark:
	cd backend && python benchmark_concurrency.py

build:
	cd frontend && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf frontend/dist
