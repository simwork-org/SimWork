# SimWork System Architecture

## Overview

This document describes the technical architecture for the SimWork platform.

SimWork is a simulation engine that places candidates inside realistic work scenarios and allows them to investigate problems by interacting with AI teammates.

The system consists of the following major components:

- Web Frontend
- Backend API
- Simulation Engine
- Agent Router
- Scenario Loader
- Telemetry Data Layer
- LLM Interface
- Investigation Logger

The architecture ensures that:

- candidates can freely investigate scenarios
- AI agents only access domain-specific data
- scenarios remain deterministic and reproducible
- candidate investigation paths are logged for evaluation

---

# High Level Architecture

Frontend (Web App)
│
▼
Backend API
│
▼
Interview Orchestrator
│
├── Scenario Loader
├── Agent Router
├── Telemetry Data Layer
├── LLM Interface
└── Investigation Logger

---

# Core Components

## 1. Frontend (Web Application)

The frontend provides the simulation interface for candidates.

Key responsibilities:

- display problem statement
- allow queries to AI teammates
- display analytics outputs and charts
- manage hypothesis lifecycle
- submit final solution

Frontend communicates with the backend via REST API.

Suggested stack:

- React or Next.js
- TailwindCSS
- REST or WebSocket for chat interaction

---

# 2. Backend API

The backend API acts as the entry point for all frontend requests.

Responsibilities:

- start simulation session
- route candidate queries
- fetch scenario data
- communicate with LLM
- log candidate activity

Suggested stack:

- Python (FastAPI)

Alternative:

- Node.js

---

# 3. Interview Orchestrator

The orchestrator controls the simulation flow.

Responsibilities:

- initialize simulation
- load scenario
- manage candidate session
- enforce query rules
- coordinate agents

Example responsibilities:

start_session()

load_scenario()

route_query()

validate_query_domain()

log_query()

submit_solution()

---

# 4. Scenario Loader

The scenario loader loads scenario datasets from the filesystem.

Scenarios are stored under:

/scenarios/

Example structure:

scenarios/
checkout_conversion_drop/
analytics/
observability/
user_signals/
scenario_config.json

The loader initializes the scenario telemetry for the simulation.

---

# 5. Telemetry Data Layer

The telemetry layer simulates product telemetry systems used in real companies.

Three telemetry domains exist.

---

## Analytics

Product behavior and metrics.

Example datasets:

analytics/
metrics_timeseries.csv
funnel_metrics.csv
segments.csv

Used by:

Data Analyst agent

---

## Observability

Engineering performance signals.

Example datasets:

observability/
service_latency.csv
error_rates.csv
deployments.json

Used by:

Developer agent

---

## User Signals

User feedback and research.

Example datasets:

user_signals/
support_tickets.csv
usability_findings.md
user_feedback.csv

Used by:

UX Researcher agent

---

# 6. Agent Router

The agent router determines which AI teammate should answer a query.

Flow:

candidate query
↓
identify selected agent
↓
validate query domain
↓
retrieve allowed telemetry
↓
generate response using LLM

Agents supported in MVP:

- Analyst Agent
- UX Agent
- Developer Agent

Each agent has restricted access to telemetry.

---

# 7. Domain Access Rules

Each agent can only access specific telemetry domains.

Agent: Analyst  
Access: analytics

Agent: UX Researcher  
Access: user_signals

Agent: Developer  
Access: observability

Agents must not access other domains.

Example restriction:

Analyst cannot access system latency data.

---

# 8. Query Validation

Candidate queries must belong to a single domain.

Example valid query:

Show checkout funnel

Example invalid query:

Did payment UI changes affect conversion?

Reason:

UI → UX domain  
Conversion → analytics domain

System response:

Your query spans multiple domains. Please ask separate questions to the relevant team members.

---

# 9. LLM Interface

The LLM generates natural language responses for agents.

Responsibilities:

- interpret candidate query
- summarize telemetry data
- generate realistic teammate responses

Example prompt structure:

You are a data analyst.

You can only answer using analytics data provided.

You cannot determine the root cause or propose solutions.

The LLM receives:

- candidate query
- filtered telemetry data
- role prompt

---

# 10. Investigation Logger

The logger records candidate activity during the simulation.

Captured data:

candidate_id  
scenario_id  
timestamp  
agent_queried  
query_text  
response_generated  
hypothesis_updates  
final_submission

Example log:

1. Analyst → show orders trend
2. Analyst → show funnel
3. Developer → check payment service latency
4. UX → user complaints about checkout

These logs are used for evaluation.

---

# 11. Simulation Session

Each candidate interaction runs inside a session.

Session state includes:

session_id  
candidate_id  
scenario_id  
current_hypothesis  
query_history  
time_remaining

Sessions end when:

- candidate submits final solution
- time limit expires

---

# 12. Scenario Determinism

All scenarios use prebuilt telemetry datasets.

This ensures:

- deterministic behavior
- reproducible simulations
- fair candidate evaluation

No dynamic data generation is used in MVP.

---

# 13. Directory Structure

Example project layout:

simwork/

frontend/
backend/

scenarios/
checkout_drop/
latency_regression/

docs/
1-product-overview.md
2-ui-ux-design.md
3-system-architecture.md
4-scenario-template.md
5-root-cause-library.md
6-api-spec.md

---

# Future Extensions

Possible improvements after MVP:

- dynamic scenario generation
- automated evaluation models
- recruiter dashboards
- integration with company telemetry systems
- multi-stage simulations
