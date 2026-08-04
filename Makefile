.PHONY: validate test install smoke api web

install:
	python -m pip install -U pip
	pip install -e "packages/hollersports[dev]"

test:
	pytest tests/ --ignore=hollersports-core -q

smoke:
	python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json

validate: install test smoke
	@echo "validate OK"

api:
	uvicorn hollersports.api.app:create_app --factory --reload --port 8000

web:
	cd packages/operator-web && npm run dev
