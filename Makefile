PYTHON ?= .venv/bin/python

.PHONY: setup lint typecheck test run refresh-data smoke

setup:
	python3.12 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest -q

run:
	$(PYTHON) -m streamlit run app.py

refresh-data:
	$(PYTHON) -m scripts.refresh_data --output-dir data

smoke:
	$(PYTHON) -m scripts.smoke_test
