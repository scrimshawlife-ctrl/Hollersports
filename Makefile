.PHONY: validate test test-unit test-integration test-golden test-calibration test-cov \
	install smoke calibration-suite backfill backfill-status api web free-first free-first-day \
	ml-e2e ml-train ml-compete ml-retrain-check ml-doc-model

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
	pytest tests/unit/test_calibration_evaluator.py tests/unit/test_settlement_history.py tests/calibration -q -m calibration

test-cov:
	pytest tests/ --ignore=hollersports-core -q \
		--cov=hollersports --cov-report=term-missing \
		--cov-config=packages/hollersports/pyproject.toml

smoke:
	python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json

calibration-suite:
	python scripts/run_calibration_suite.py --out docs/evidence/calibration_suite.last.json

# Multi-fixture accumulation into data/backfill (grows calibration sample).
# Hermes: see docs/agents/HERMES_BACKFILL.md — run backfill-status first.
backfill-status:
	python scripts/backfill_status.py

backfill:
	python scripts/backfill_fixtures.py --out docs/evidence/backfill_calibration.last.json
	python scripts/backfill_status.py

validate: install test smoke calibration-suite
	@echo "validate OK"

api:
	uvicorn hollersports.api.app:create_app --factory --reload --port 8000

web:
	cd packages/operator-web && npm run dev

# Optional live observation (ESPN free; Odds API if THE_ODDS_API_KEY set). Advisory only.
free-first:
	python scripts/holler_free_first_ingest.py --out out/free_first_observation.json

# Closed free-first day → compete → paper → ESPN settle → calibration bank.
# Prefer injected JSON for CI; live finals need --fetch-espn-finals (network).
# Example (injected): python scripts/free_first_operator_day.py --espn-raw ... --odds-raw ... --settle-espn-raw ...
FREE_FIRST_LEAGUES ?= NBA
free-first-day:
	python scripts/free_first_operator_day.py --leagues $(FREE_FIRST_LEAGUES) --fetch-espn-finals \
		--data-root data/backfill --out docs/evidence/free_first_day.last.json

# Track F research ML (offline fixtures; advisory only; no sklearn required).
# Train on day001+day002, apply day003 → docs/evidence/ml_pipeline_e2e.last.json
ml-e2e:
	python scripts/holler/ml_e2e.py

ml-train:
	python scripts/holler/train_gbm.py fixtures/day001 fixtures/day002 --out-dir data/ml

# Annotate day003 + strategy competition with explicit model-edge opt-in (offline demo).
ml-compete:
	python scripts/holler/ml_compete_day.py \
		--fixture-day fixtures/day003 \
		--train-days fixtures/day001 fixtures/day002 \
		--allow-model-edge \
		--out-dir data/ml/compete

# Advisory retrain proposal only (never auto-trains).
ml-retrain-check:
	python scripts/holler/ml_retrain_check.py

ml-doc-model:
	python scripts/holler/doc_model.py --ensemble data/ml/ensemble.json
