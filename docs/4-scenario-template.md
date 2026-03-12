# SimWork Scenario Template

## Overview

This document defines how simulation scenarios are structured in SimWork.

Each scenario represents a **realistic work situation** where a candidate must investigate a problem and identify the root cause by interacting with AI teammates.

All scenarios must follow a **consistent structure** so the simulation engine can load and execute them deterministically.

Scenarios simulate signals from three product telemetry domains:

- Analytics (product metrics)
- Observability (engineering signals)
- User Signals (UX / user feedback)

Candidates must combine signals from multiple domains to determine the root cause.

---

# Scenario Directory Structure

Each scenario should be stored as a folder inside:

```
/scenarios/
```

Example:

```
scenarios/
    checkout_conversion_drop/
        scenario_config.json
        analytics/
        observability/
        user_signals/
```

---

# Scenario Folder Layout

Example scenario structure:

```
checkout_conversion_drop/

    scenario_config.json

    analytics/
        metrics_timeseries.csv
        funnel_metrics.csv
        segments.csv

    observability/
        service_latency.csv
        error_rates.csv
        deployments.json

    user_signals/
        support_tickets.csv
        usability_findings.md
        user_feedback.csv
```

---

# scenario_config.json

The scenario configuration file contains metadata about the simulation.

Example:

```
{
  "scenario_id": "checkout_conversion_drop",
  "title": "Checkout Conversion Drop",
  "difficulty": "medium",
  "industry": "food_delivery",
  "product": "FoodDash",

  "problem_statement": "Weekly orders have dropped by 18% over the past month. Investigate the issue and propose a recovery plan.",

  "root_cause": "payment_service_latency",

  "expected_investigation_path": [
    "orders_trend",
    "checkout_funnel",
    "segment_analysis",
    "payment_service_latency",
    "user_payment_feedback"
  ]
}
```

The `root_cause` field is hidden from candidates and used internally by the system.

---

# Telemetry Domains

SimWork scenarios simulate telemetry systems used in real companies.

Three domains exist.

---

# Analytics Domain

Represents product analytics and business metrics.

Typical queries answered by the **Data Analyst** agent.

Example datasets:

```
analytics/
    metrics_timeseries.csv
    funnel_metrics.csv
    segments.csv
```

---

## metrics_timeseries.csv

Tracks product KPIs over time.

Example:

```
date,orders,conversion_rate
2025-01-01,52000,0.22
2025-01-08,51000,0.21
2025-01-15,47000,0.18
2025-01-22,42000,0.14
```

---

## funnel_metrics.csv

Represents the product funnel.

Example:

```
step,conversion_rate
app_open,1.0
restaurant_view,0.76
add_to_cart,0.41
checkout,0.27
payment,0.14
order_success,0.13
```

---

## segments.csv

Segment performance metrics.

Example:

```
segment,checkout_conversion
new_users,0.09
returning_users,0.18
```

---

# Observability Domain

Represents engineering system signals.

Accessed by the **Developer** agent.

Example datasets:

```
observability/
    service_latency.csv
    error_rates.csv
    deployments.json
```

---

## service_latency.csv

Example:

```
service,week1,week2,week3,week4
payment_service,1.1,1.2,2.4,2.8
checkout_service,0.9,1.0,1.1,1.1
```

---

## error_rates.csv

Example:

```
service,error_rate
payment_service,3.2
checkout_service,0.4
```

---

## deployments.json

Example:

```
[
  {
    "date": "2025-01-15",
    "service": "payment_service",
    "change": "new payment gateway integration"
  }
]
```

---

# User Signals Domain

Represents UX research and user feedback.

Accessed by the **UX Researcher** agent.

Example datasets:

```
user_signals/
    support_tickets.csv
    usability_findings.md
    user_feedback.csv
```

---

## support_tickets.csv

Example:

```
ticket_id,issue
1001,payment failed multiple times
1002,unable to complete checkout
1003,payment retry not available
```

---

## usability_findings.md

Example:

```
User testing indicates that users abandon checkout when payment fails.

Several users attempted payment multiple times but could not retry easily.
```

---

## user_feedback.csv

Example:

```
feedback
payment keeps failing
checkout process confusing
unable to retry payment
```

---

# Investigation Signals

Each scenario should contain signals across **multiple domains** that lead toward the root cause.

Example signal chain:

```
Orders drop
     ↓
Checkout funnel drop
     ↓
Payment service latency increase
     ↓
User complaints about payment failure
```

Candidates must connect these signals to determine the root cause.

---

# Scenario Design Guidelines

When creating scenarios:

1. The problem must be observable through analytics metrics.
2. Multiple signals should exist across different domains.
3. No single agent should reveal the root cause directly.
4. The investigation path should mimic real product debugging workflows.

---

# Difficulty Levels

Scenarios can vary in complexity.

### Easy

Clear signals across domains.

### Medium

Multiple possible hypotheses.

### Hard

Multiple interacting issues or misleading signals.

---

# Future Scenario Extensions

Future scenarios may include:

- A/B experiment failures
- supply-side marketplace problems
- infrastructure outages
- recommendation algorithm issues
- onboarding funnel regressions
