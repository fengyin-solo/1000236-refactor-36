.PHONY: install backend frontend prepare check smoke verify

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

prepare:
	cd backend && .venv/bin/python scripts/prepare_data.py

check:
	cd backend && .venv/bin/python scripts/check_env.py

smoke:
	cd backend && .venv/bin/python scripts/smoke_check.py

verify: prepare check

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev
