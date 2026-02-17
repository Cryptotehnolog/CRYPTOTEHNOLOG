# ==================== CRYPTOTEHNOLOG Makefile ====================
# Convenient commands for development and testing

.PHONY: help install install-dev test test-unit test-integration test-e2e lint format type-check security-check clean build run dev-up dev-down dev-logs dev-restart check-env setup-env rust-build rust-test rust-clippy rust-fmt docker-build docker-up docker-down docker-logs docker-clean docker-restart coverage-report

# Default target
help:
	@echo "CRYPTOTEHNOLOG v1.0.0 - Available commands:"
	@echo ""
	@echo "  ==================== Environment Setup ===================="
	@echo "  make install           - Install Python dependencies"
	@echo "  make install-dev       - Install development dependencies"
	@echo "  make check-env         - Check if environment is set up correctly"
	@echo "  make setup-env         - Set up development environment"
	@echo ""
	@echo "  ==================== Python ===================="
	@echo "  make test              - Run all tests"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-e2e          - Run end-to-end tests only"
	@echo "  make lint              - Run linter (ruff)"
	@echo "  make format            - Format code (black, ruff)"
	@echo "  make type-check        - Run type checker (mypy)"
	@echo "  make security-check    - Run security scan (bandit, safety)"
	@echo "  make coverage-report   - Generate HTML coverage report"
	@echo ""
	@echo "  ==================== Rust ===================="
	@echo "  make rust-build        - Build Rust components"
	@echo "  make rust-test         - Run Rust tests"
	@echo "  make rust-clippy       - Run Rust linter (clippy)"
	@echo "  make rust-fmt          - Format Rust code"
	@echo ""
	@echo "  ==================== Docker ===================="
	@echo "  make docker-build      - Build Docker images"
	@echo "  make docker-up         - Start Docker services"
	@echo "  make docker-down       - Stop Docker services"
	@echo "  make docker-logs       - View Docker logs"
	@echo "  make docker-clean      - Clean Docker volumes and containers"
	@echo "  make docker-restart    - Restart Docker services"
	@echo ""
	@echo "  ==================== Development ===================="
	@echo "  make dev-up            - Start development environment"
	@echo "  make dev-down          - Stop development environment"
	@echo "  make dev-logs          - View development logs"
	@echo "  make dev-restart       - Restart development environment"
	@echo ""
	@echo "  ==================== Cleanup ===================="
	@echo "  make clean             - Clean build artifacts and cache"
	@echo ""

# ==================== Environment Setup ====================
install:
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install pre-commit
	pre-commit install

check-env:
	@echo "Checking environment..."
	@python --version || (echo "❌ Python not found" && exit 1)
	@rustc --version || (echo "❌ Rust not found" && exit 1)
	@docker --version || (echo "❌ Docker not found" && exit 1)
	@pip list | grep pydantic > /dev/null || (echo "❌ Python dependencies not installed" && exit 1)
	@echo "✅ Environment check passed!"

setup-env:
	@echo "Setting up development environment..."
	@python -m venv venv
	@echo "✅ Virtual environment created. Activate with: .\\venv\\Scripts\\Activate.ps1 (Windows) or source venv/bin/activate (Linux/Mac)"
	@make install-dev

# ==================== Python ====================
test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v -m unit

test-integration:
	pytest tests/integration/ -v -m integration

test-e2e:
	pytest tests/e2e/ -v -m e2e

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	black src/ tests/
	ruff format src/ tests/

type-check:
	mypy src/

security-check:
	bandit -r src/ -f screen
	safety check -r requirements.txt

coverage-report:
	pytest tests/ --cov=src --cov-report=html
	@echo "Coverage report generated at htmlcov/index.html"

# ==================== Rust ====================
rust-build:
	cd rust_components && cargo build --release

rust-test:
	cd rust_components && cargo test

rust-clippy:
	cd rust_components && cargo clippy -- -D warnings

rust-fmt:
	cd rust_components && cargo fmt

# ==================== Docker ====================
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d redis timescaledb
	@echo "✅ Core services started. Use 'make docker-up-observability' to start Grafana/Prometheus."

docker-up-observability:
	docker-compose --profile observability up -d

docker-up-all:
	docker-compose --profile observability --profile tools up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	docker-compose down -v
	docker system prune -f

docker-restart:
	docker-compose restart

# ==================== Development ====================
dev-up: docker-up
	@echo "✅ Development environment started!"
	@echo "Redis: localhost:6379"
	@echo "PostgreSQL: localhost:5432"
	@echo "Grafana: http://localhost:3000 (admin/admin_dev)"

dev-down: docker-down
	@echo "✅ Development environment stopped!"

dev-logs:
	docker-compose logs -f

dev-restart: docker-down docker-up
	@echo "✅ Development environment restarted!"

# ==================== Cleanup ====================
clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type f -name "*.db" -delete 2>/dev/null || true
	@find . -type f -name "*.log" -delete 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .cache/ 2>/dev/null || true
	@echo "✅ Clean completed!"

# ==================== Pre-commit ====================
pre-commit-all:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate
