# SimWork

SimWork is an MVP platform for simulated product investigations. Candidates enter a realistic scenario, question AI teammates inside strict telemetry boundaries, build hypotheses, and submit a final recommendation.

The implementation in this repository follows the docs in [`docs/`](./docs), with the current MVP covering:

- FastAPI backend with scenario loading, domain-restricted query routing, LLM orchestration hooks, and SQLite activity logging
- Next.js frontend using the three stitched UI screens as reusable components
- Example deterministic scenario in [`scenarios/checkout_conversion_drop`](./scenarios/checkout_conversion_drop)
- Local fallback response generation when no live LLM provider is reachable

## Project Structure

```text
backend/
  api/
  simulation_engine/
  agent_router/
  scenario_loader/
  telemetry_layer/
  llm_interface/
  investigation_logger/

frontend/
scenarios/
docs/
```

## Local Setup

1. Copy the environment template.

```bash
cp .env.example .env
```

2. Install backend dependencies with `uv`.

```bash
uv sync --dev
```

3. Install frontend dependencies.

```bash
cd frontend
npm install
cd ..
```

4. Start the backend.

```bash
make backend
```

5. Start the frontend in a second terminal.

```bash
cd frontend
npm run dev
```

Frontend: `http://localhost:3000`  
Backend API: `http://localhost:8000/api/v1`

## Environment Variables

The backend reads the provider configuration from `.env`:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `OLLAMA_ENDPOINT`
- `MODEL_PROVIDER`
- `MODEL_NAME`

If a configured provider is unavailable, the MVP falls back to deterministic telemetry summaries so the investigation flow still works locally.

## API Coverage

Implemented endpoints:

- `GET /api/v1/scenarios`
- `POST /api/v1/sessions/start`
- `GET /api/v1/sessions/{session_id}/scenario`
- `POST /api/v1/sessions/{session_id}/query`
- `POST /api/v1/sessions/{session_id}/hypothesis`
- `GET /api/v1/sessions/{session_id}/history`
- `GET /api/v1/sessions/{session_id}/status`
- `POST /api/v1/sessions/{session_id}/submit`

## Docker

Backend Docker image:

```bash
docker build -f backend/Dockerfile -t simwork-backend .
```

Compose setup:

```bash
docker compose up --build
```

## Verification

Validated locally with:

```bash
uv run pytest
cd frontend && npm run build
```
