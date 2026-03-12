# SimWork Root Cause Library

## Overview

This document defines the **initial root cause scenarios** supported by SimWork.

Each simulation scenario is built around a **hidden root cause** that candidates must discover through investigation.

Root causes must produce signals across the three telemetry domains used by SimWork:

- Analytics (product metrics)
- Observability (engineering/system signals)
- User Signals (UX feedback and user reports)

The goal is to ensure that the candidate must combine **multiple signals across different domains** to determine the true cause.

---

# Root Cause Design Principles

Each root cause should satisfy the following:

1. Observable through product metrics.
2. Supported by signals across multiple telemetry systems.
3. Discoverable through investigation.
4. Not directly revealed by any single AI agent.
5. Realistic for modern product organizations.

---

# Root Cause 1 — Payment Service Latency

## Description

Payment processing latency increases due to infrastructure changes.

## Analytics Signals

- Orders decline
- Checkout → Payment conversion drop
- Increased checkout abandonment

## Observability Signals

- Payment service latency increase
- Error rates increase
- Deployment affecting payment gateway

## User Signals

- Support tickets reporting payment failure
- Feedback about payment not completing
- Users retrying checkout multiple times

---

# Root Cause 2 — Checkout UX Regression

## Description

A redesign of the checkout page introduces usability friction.

## Analytics Signals

- Drop in Add-to-Cart → Checkout conversion
- Increased checkout abandonment

## Observability Signals

- No significant engineering issues
- Normal service latency

## User Signals

- Usability research shows confusion with new layout
- Support tickets mentioning difficulty completing checkout
- User feedback complaining about UI changes

---

# Root Cause 3 — API Latency Regression

## Description

Backend API latency increases due to inefficient database queries.

## Analytics Signals

- Session duration drops
- Page load abandonment increases
- Conversion decreases

## Observability Signals

- API latency spike
- Increased database query time
- Recent backend deployment

## User Signals

- Feedback mentioning slow loading
- Complaints about app responsiveness

---

# Root Cause 4 — Supply Side Marketplace Drop

## Description

Marketplace supply decreases due to partner churn or inventory shortage.

## Analytics Signals

- Search-to-order conversion decreases
- Available inventory drops
- Order success rate decreases

## Observability Signals

- System performance normal
- No major engineering issues

## User Signals

- Feedback indicating items unavailable
- Complaints about limited selection

---

# Root Cause 5 — Failed Experiment Rollout

## Description

An A/B experiment negatively impacts user behavior.

## Analytics Signals

- Conversion drop in experiment cohort
- Metrics decline after experiment launch

## Observability Signals

- Feature flag rollout detected
- Experiment deployment event logged

## User Signals

- Feedback indicating confusion with new feature
- UX research showing decreased usability

---

# Root Cause 6 — Recommendation Algorithm Issue

## Description

Changes in recommendation algorithm reduce product relevance.

## Analytics Signals

- Decrease in click-through rate
- Reduced engagement with recommended items
- Lower conversion from discovery flows

## Observability Signals

- Recommendation model deployment event
- Increased response time in recommendation service

## User Signals

- Feedback saying recommendations are irrelevant
- Lower satisfaction scores

---

# Root Cause Mapping to Telemetry Domains

| Root Cause                     | Analytics | Observability | User Signals |
| ------------------------------ | --------- | ------------- | ------------ |
| Payment Service Latency        | ✓         | ✓             | ✓            |
| Checkout UX Regression         | ✓         | ✗             | ✓            |
| API Latency Regression         | ✓         | ✓             | ✓            |
| Supply Marketplace Drop        | ✓         | ✗             | ✓            |
| Failed Experiment Rollout      | ✓         | ✓             | ✓            |
| Recommendation Algorithm Issue | ✓         | ✓             | ✓            |

---

# Scenario Generation

Each root cause can generate multiple scenarios by changing:

- industry (food delivery, ecommerce, ride sharing)
- product funnel structure
- telemetry values
- user feedback wording

Example:

Payment Service Latency could produce scenarios for:

- Food delivery checkout
- Ecommerce payment processing
- Ride sharing payment confirmation

---

# Root Cause Usage

The scenario generator uses the root cause library to construct scenarios.

Process:

1. Select root cause
2. Generate telemetry signals
3. Populate scenario datasets
4. Load scenario into simulation engine

---

# Future Extensions

Additional root causes may include:

- authentication service outage
- onboarding funnel regression
- search ranking bug
- inventory synchronization issues
- notification delivery failure

The root cause library will expand as new simulation scenarios are added.
