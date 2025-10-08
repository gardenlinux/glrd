# GLRD Makefile

.PHONY: help install test test-unit test-integration test-all lint clean

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	poetry install

install-dev: ## Install development dependencies
	poetry install --with dev

test: ## Run all tests
	poetry run pytest

test-unit: ## Run unit tests only
	poetry run pytest -m unit

test-integration: ## Run integration tests only
	poetry run pytest -m integration

test-all: ## Run all tests with coverage
	poetry run pytest --cov=glrd --cov-report=html --cov-report=term

lint: ## Run linting
	poetry run flake8 --max-line-length 110 glrd/ tests/
	poetry run black --check glrd/ tests/
	poetry run autopep8 --diff --max-line-length 110 -r glrd/ tests/

format: ## Format code
	poetry run black glrd/ tests/

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
