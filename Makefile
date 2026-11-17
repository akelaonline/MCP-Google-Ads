.PHONY: install install-dev install-certified smoke test lint format check lifecycle

install:
	python -m pip install -e .

install-dev:
	python -m pip install -e ".[dev]"

install-certified:
	python -m pip install -e ".[dev,auth]" -c constraints-certified.txt
	python -m pip check

lifecycle:
	python scripts/stdio_lifecycle_test.py

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
	python scripts/stdio_lifecycle_test.py
