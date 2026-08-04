.PHONY: validate test test-unit test-integration test-golden test-calibration test-cov \
	install smoke calibration-suite api web free-first

install:
	python -m pip install -U pip
	pip install -e "packages/hollersports[dev]"

test:
	pytest tests/ --ignore=hollersports-core -q

test-unit:
	pytest tests/unit -q -m "unit or not integration"

test-integration:
	pytest tests/integration -q

test-golden:
	pytest tests/golden tests/calibration -q -m "golden or calibration"

test-calibration:
	pytest tests/unit/test_calibration_evaluator.py tests/calibration -q -m calibration

test-cov:
	pytest tests/ --ignore=hollersports-core -q \
		--cov=hollersports --cov-report=term-missing \
		--cov-config=packages/hollersports/pyproject.toml

smoke:
	python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json

calibration-suite:
	python scripts/run_calibration_suite.py --out docs/evidence/calibration_suite.last.json

validate: install test smoke calibration-suite
	@echo "validate OK"

api:
	uvicorn hollersports.api.app:create_app --factory --reload --port 8000

web:
	cd packages/operator-web && npm run dev

# Optional live observation (ESPN free; Odds API if THE_ODDS_API_KEY set). Advisory only.
free-first:
	python scripts/holler_free_first_ingest.py --out out/free_first_observation.json
