.PHONY: help install dev-start dev-stop test lint format clean

help:
	@echo "Visual Search Project - Available Commands"
	@echo "==========================================="
	@echo "install      - Install dependencies with Poetry"
	@echo "dev-start    - Start development environment (Docker services)"
	@echo "dev-stop     - Stop development environment"
	@echo "init-db      - Initialize database and load sample data"
	@echo "api          - Start FastAPI server"
	@echo "worker       - Start Celery worker"
	@echo "test         - Run tests"
	@echo "test-cov     - Run tests with coverage"
	@echo "lint         - Run linters (flake8, mypy)"
	@echo "format       - Format code (black, isort)"
	@echo "clean        - Clean up generated files"

install:
	poetry install

dev-start:
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Services started! Check status with: docker-compose ps"

dev-stop:
	docker-compose down

init-db:
	poetry run python scripts/load_sample_data.py

api:
	poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8008 --reload

worker:
	poetry run celery -A app.workers.celery_app worker --loglevel=info

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=app --cov-report=html --cov-report=term

lint:
	poetry run flake8 app tests
	poetry run mypy app

format:
	poetry run black app tests
	poetry run isort app tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage

