# Makefile for ccmaxproxy
# Cross-platform commands for development and testing

.PHONY: help test test-unit test-integration test-smoke test-cov test-watch lint format clean install dev-install run

# Default target
help:
	@echo "ccmaxproxy Development Commands"
	@echo "================================"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests (unit + integration)"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-smoke        - Run smoke tests (requires ANTHROPIC_OAUTH_TOKEN)"
	@echo "  make test-cov          - Run tests with coverage report"
	@echo "  make test-watch        - Auto-run tests on file changes"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run linters (ruff, mypy)"
	@echo "  make format            - Format code with black"
	@echo "  make check             - Run linters without fixing (for CI)"
	@echo ""
	@echo "Setup:"
	@echo "  make install           - Install production dependencies"
	@echo "  make dev-install       - Install development dependencies"
	@echo "  make clean             - Remove build artifacts and cache"
	@echo ""
	@echo "Running:"
	@echo "  make run               - Start the proxy server"
	@echo "  make run-headless      - Start in headless mode"
	@echo ""

# Testing
test:
	pytest tests/unit/ tests/integration/ -v

test-unit:
	pytest tests/unit/ -v -m unit

test-integration:
	pytest tests/integration/ -v -m integration

test-smoke:
	@echo "⚠️  WARNING: This will make real API calls!"
	@echo "Make sure ANTHROPIC_OAUTH_TOKEN is set"
	@echo ""
	pytest tests/smoke/ -v -m smoke

test-cov:
	pytest --cov=. --cov-report=term-missing --cov-report=html --cov-report=json
	@echo ""
	@echo "📊 Coverage report generated:"
	@echo "  - Terminal: See above"
	@echo "  - HTML: htmlcov/index.html"
	@echo "  - JSON: coverage.json"

test-watch:
	pytest-watch -- -v

# Code Quality
lint:
	@echo "Running ruff..."
	ruff check . --fix
	@echo ""
	@echo "Running mypy..."
	mypy . --ignore-missing-imports

format:
	@echo "Formatting code with black..."
	black .
	@echo ""
	@echo "Running ruff..."
	ruff check . --fix

check:
	@echo "Running ruff (no fix)..."
	ruff check .
	@echo ""
	@echo "Running black (check only)..."
	black --check .
	@echo ""
	@echo "Running mypy..."
	mypy . --ignore-missing-imports

# Setup
install:
	pip install -r requirements.txt

dev-install: install
	pip install -r requirements-dev.txt

clean:
	@echo "Cleaning build artifacts..."
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.json
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Clean complete"

# Running
run:
	python cli.py

run-headless:
	python cli.py --headless

# Git hooks (optional)
install-hooks:
	@echo "Installing pre-commit hooks..."
	@echo "#!/bin/sh" > .git/hooks/pre-commit
	@echo "make format" >> .git/hooks/pre-commit
	@echo "make check" >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Pre-commit hooks installed"
