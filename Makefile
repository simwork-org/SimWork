.PHONY: backend frontend test install-backend install-frontend

backend:
	uv run uvicorn backend.api.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	uv run pytest

install-backend:
	uv sync --dev

install-frontend:
	cd frontend && npm install
