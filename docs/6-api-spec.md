# SimWork API Specification

## Overview

This document defines the backend API endpoints required to run the SimWork simulation platform.

The APIs allow the frontend to:

- start a simulation session
- send queries to AI teammates
- retrieve scenario information
- manage hypotheses
- submit final solutions
- log candidate activity

All APIs are designed to be **stateless REST endpoints**, except for session state managed by the backend.

Base URL example:

```
/api/v1
```

---

# Authentication (MVP)

For MVP, authentication can be minimal.

Options:

- session-based token
- temporary candidate session ID

Example:

```
Authorization: Bearer <session_token>
```

---

# 1. Start Simulation Session

Creates a new simulation session for a candidate.

### Endpoint

```
POST /sessions/start
```

### Request

```
{
  "candidate_id": "candidate_123",
  "scenario_id": "checkout_conversion_drop"
}
```

### Response

```
{
  "session_id": "session_abc123",
  "scenario_id": "checkout_conversion_drop",
  "problem_statement": "Weekly orders have dropped by 18% over the past month. Investigate the issue and propose a recovery plan.",
  "available_agents": [
    "analyst",
    "ux_researcher",
    "developer"
  ],
  "time_limit_minutes": 30
}
```

---

# 2. Get Scenario Details

Returns the scenario problem statement and context.

### Endpoint

```
GET /sessions/{session_id}/scenario
```

### Response

```
{
  "scenario_id": "checkout_conversion_drop",
  "title": "Checkout Conversion Drop",
  "problem_statement": "Weekly orders have dropped by 18% over the past month."
}
```

---

# 3. Send Query to Agent

Candidate asks a question to a specific AI teammate.

### Endpoint

```
POST /sessions/{session_id}/query
```

### Request

```
{
  "agent": "analyst",
  "query": "Show checkout funnel conversion over the last 4 weeks"
}
```

Valid agents:

```
analyst
ux_researcher
developer
```

### Response

```
{
  "agent": "analyst",
  "response": "Checkout to payment conversion dropped from 22% to 14% over the past 4 weeks.",
  "data_visualization": {
    "type": "funnel",
    "data": [
      {"step": "app_open", "value": 1.0},
      {"step": "restaurant_view", "value": 0.76},
      {"step": "add_to_cart", "value": 0.41},
      {"step": "checkout", "value": 0.27},
      {"step": "payment", "value": 0.14}
    ]
  }
}
```

---

# 4. Validate Query Domain

Ensures the query belongs to the selected agent's domain.

If a query spans multiple domains, the system returns an error.

### Example Response

```
{
  "error": "query_domain_violation",
  "message": "Your query spans multiple domains. Please ask separate questions to the relevant team members."
}
```

---

# 5. Submit Hypothesis

Candidate proposes or updates a hypothesis during investigation.

### Endpoint

```
POST /sessions/{session_id}/hypothesis
```

### Request

```
{
  "hypothesis": "Payment gateway latency is causing checkout failures"
}
```

### Response

```
{
  "status": "saved",
  "hypothesis_version": 2
}
```

The system should allow multiple hypothesis updates.

---

# 6. Get Query History

Returns the investigation history for the session.

### Endpoint

```
GET /sessions/{session_id}/history
```

### Response

```
{
  "queries": [
    {
      "timestamp": "2026-03-12T10:10:00Z",
      "agent": "analyst",
      "query": "Show orders trend",
      "response": "Orders declined from 52k to 42k."
    },
    {
      "timestamp": "2026-03-12T10:12:00Z",
      "agent": "developer",
      "query": "Any recent deployments to payment service?",
      "response": "Payment gateway integration deployed 3 weeks ago."
    }
  ]
}
```

---

# 7. Submit Final Solution

Candidate submits final root cause and action plan.

### Endpoint

```
POST /sessions/{session_id}/submit
```

### Request

```
{
  "root_cause": "Payment service latency increase",
  "proposed_actions": [
    "reduce payment gateway latency",
    "add payment retry logic",
    "improve payment UX feedback"
  ],
  "summary": "Payment latency increase caused checkout failures leading to order drop."
}
```

### Response

```
{
  "status": "submitted",
  "session_complete": true
}
```

---

# 8. Session Status

Returns the current state of the simulation session.

### Endpoint

```
GET /sessions/{session_id}/status
```

### Response

```
{
  "session_id": "session_abc123",
  "scenario_id": "checkout_conversion_drop",
  "time_remaining_minutes": 12,
  "current_hypothesis": "Payment gateway latency",
  "queries_made": 7
}
```

---

# 9. Scenario List

Returns available scenarios.

### Endpoint

```
GET /scenarios
```

### Response

```
{
  "scenarios": [
    {
      "id": "checkout_conversion_drop",
      "title": "Checkout Conversion Drop",
      "difficulty": "medium"
    },
    {
      "id": "api_latency_regression",
      "title": "API Latency Regression",
      "difficulty": "medium"
    }
  ]
}
```

---

# Error Handling

Standard error response format.

```
{
  "error": "error_code",
  "message": "Human readable explanation"
}
```

Common errors:

```
invalid_session
invalid_agent
query_domain_violation
scenario_not_found
```

---

# Logging Requirements

The backend must log the following for evaluation:

- session_id
- candidate_id
- scenario_id
- query_text
- agent_used
- timestamp
- hypothesis_updates
- final_submission

Logs should be stored in a database or structured event log.

---

# Future API Extensions

Future versions may include:

- automated scoring API
- recruiter dashboards
- real company telemetry integrations
- multi-stage simulations
