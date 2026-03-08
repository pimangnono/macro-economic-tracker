PYTHON ?= python3
PYTHONPATH ?= apps/api

.PHONY: migrate seed test-api lint-api ingestion-worker

migrate:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m app.scripts.migrate

seed:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m app.scripts.seed_demo

test-api:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest apps/api/tests

lint-api:
	ruff check apps/api/app apps/api/tests

ingestion-worker:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m app.scripts.run_source_scheduler
