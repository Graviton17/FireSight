.PHONY: api-install api-run api-test api-lint firmware-build

api-install:
	python -m pip install -e "apps/backend[dev]"

api-run:
	cd apps/backend && uvicorn firesight_backend.main:app --reload --host 0.0.0.0 --port 8000

api-test:
	cd apps/backend && python -m pytest

api-lint:
	cd apps/backend && ruff check src tests

firmware-build:
	pio run --project-dir apps/firmware/esp32
