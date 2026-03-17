# SimWork

SimWork is a simulation platform for evaluating how candidates investigate ambiguous product problems, use evidence, collaborate with AI teammates, and communicate decisions.

The current repository ships a production-ready `v1.0.0` baseline with:

- a FastAPI backend for scenario loading, session orchestration, evidence logging, scoring, and health checks
- a Next.js frontend for investigation, evidence board, final submission, and review flows
- scenario data and evaluation logic for the current PM simulation experience
- minimum CI plus deployment configuration for Vercel and Railway

## Repository Structure

```text
backend/            FastAPI application, routing, scoring, persistence, tests
frontend/           Next.js application
scenarios/          Scenario data and configuration
docs/releases/      Versioned release notes
CHANGELOG.md        Durable change history
RELEASING.md        Release process
.local/docs/        Ignored local planning, research, and reference material
```

## Documentation Policy

- `README.md` is the current shared project overview.
- `CHANGELOG.md` is the canonical version history.
- `RELEASING.md` defines the release process.
- `docs/releases/` contains one release note per shipped version.
- `.local/docs/` is for local-only planning, research, PRDs, notes, and reference files that should not be committed.

## Local Setup

1. Copy the backend environment template.

```bash
cp backend/.env.example backend/.env
```

2. Review the frontend environment template.

```bash
cp frontend/.env.example frontend/.env.local
```

3. Install backend dependencies.

```bash
cd backend
uv sync
cd ..
```

4. Install frontend dependencies.

```bash
cd frontend
npm install
cd ..
```

5. Start the backend.

```bash
make backend
```

6. Start the frontend in a second terminal.

```bash
cd frontend
npm run dev
```

Frontend: `http://localhost:3000`
Backend API: `http://localhost:8000/api/v1`
Backend health: `http://localhost:8000/health`

## Environment Variables

Backend variables are documented in `backend/.env.example`, including:

- `LLM_PROVIDER`
- `LLM_MODEL`
- provider API keys
- `DATABASE_URL`
- `CORS_ORIGINS`

Frontend variables are documented in `frontend/.env.example`, including:

- `NEXT_PUBLIC_API_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `NEXTAUTH_SECRET`
- `NEXTAUTH_URL`

## Verification

Backend:

```bash
cd backend
uv run ruff check .
uv run pytest tests/ -v
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Deployment

- Frontend deploys from `main` via Vercel.
- Backend deploys from `main` via Railway.
- Railway health checks target `/health`.
- GitHub Actions gate pull requests to `develop` and `main`.
