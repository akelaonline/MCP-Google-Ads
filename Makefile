.PHONY: install install-dev smoke test lint format check

install:
	python -m pip install -e .

install-dev:
	python -m pip install -e ".[dev]"

smoke:
	python scripts/smoke_test.py

test:
	pytest tests/ -v

lint:
	ruff check src tests scripts

format:
	ruff format src tests scripts

check:
	python -m pip check
	python scripts/smoke_test.py
	ruff check src tests scripts
	pytest tests/ -v
