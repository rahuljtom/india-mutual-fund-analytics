PY := .venv/bin/python
export PYTHONPATH := src

.PHONY: setup download build charts test lint check all

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

download:           # about 2.5 GB uncompressed, 33 windows of 90 days; safe to re-run, finished windows are skipped
	$(PY) -m mfa.download --start 2018-01-01 --end 2025-12-31

build:              # parse raw reports, build the DuckDB warehouse, export outputs/tables/*.csv
	$(PY) -m mfa.pipeline

charts:
	$(PY) -m mfa.charts

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/sqlfluff lint sql

check: lint test

all: download build charts check
