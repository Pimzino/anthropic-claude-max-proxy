# Makefile for ccmaxproxy
# Cross-platform commands for development and testing

.PHONY: help lint format clean install dev-install run

# Default target
help:
	@echo "ccmaxproxy Development Commands"
	@echo "================================"
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
	rm -rf .mypy_cache
	rm -rf .ruff_cache
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
