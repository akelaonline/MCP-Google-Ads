.PHONY: install test smoke lint format clean

VENV_PYTHON ?= .venv/bin/python

install:
	$(VENV_PYTHON) -m pip install -e ".[dev]"

test:
	$(VENV_PYTHON) -m pytest tests/ -q

smoke:
	$(VENV_PYTHON) scripts/smoke_test.py

lint:
	$(VENV_PYTHON) -m ruff check src tests || true

format:
	$(VENV_PYTHON) -m ruff format src tests || true

clean:
	find src tests -type d -name __pycache__ -exec rm -rf {} +
	find src tests -type f -name '*.pyc' -delete
	rm -rf build dist *.egg-info .pytest_cache
