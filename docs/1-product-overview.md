# SimWork Product Overview

## Introduction

SimWork is a platform that simulates real work environments to evaluate how people investigate problems, make decisions, and execute solutions.

Instead of answering theoretical interview questions, candidates are placed inside realistic work scenarios where they must collaborate with AI teammates to diagnose problems and propose solutions.

The goal is to evaluate **how people actually operate in a work environment**, not just how they answer questions.

---

# Core Idea

SimWork recreates the process of solving real work problems.

In a typical simulation:

1. A candidate is introduced to a problem.
2. The candidate investigates the issue by interacting with AI teammates.
3. Each teammate provides partial information based on their domain.
4. The candidate connects signals from multiple sources.
5. The candidate identifies the root cause and proposes a solution.

This process mirrors how problems are solved inside real companies.

---

# Simulation Workflow

Each SimWork simulation follows a structured workflow.

### Step 1 — Problem Introduction

The candidate receives a problem statement.

Example:

Orders dropped by 18% over the last month.

The candidate's goal is to investigate the issue and propose a recovery plan.

---

### Step 2 — Investigation

The candidate investigates the problem by asking questions to different team members.

Available AI teammates may include:

- Data Analyst
- UX Researcher
- Developer

Each teammate provides access to a different set of information.

---

### Step 3 — Hypothesis Formation

The candidate forms hypotheses about the cause of the issue.

Example:

- Checkout UX is confusing
- Payment service latency increased
- Users are abandoning after payment failure

The candidate can update or replace hypotheses during the investigation.

---

### Step 4 — Evidence Gathering

The candidate gathers supporting evidence from multiple sources.

Example investigation path:

1. Check order trends
2. Analyze conversion funnel
3. Segment users
4. Check recent deployments
5. Review user feedback

---

### Step 5 — Root Cause Identification

The candidate identifies the most likely root cause.

Example:

Payment gateway latency increased, causing checkout failures.

---

### Step 6 — Solution Proposal

The candidate proposes actions to resolve the issue.

Example:

- reduce payment latency
- add payment retry
- improve payment UX

---

# AI Teammates

SimWork uses multiple AI agents that simulate real team roles.

Each agent represents a different domain within a company.

### Data Analyst

Provides access to product analytics.

Typical information:

- metric trends
- conversion funnels
- user segmentation
- experiment results

---

### UX Researcher

Provides access to user research signals.

Typical information:

- usability findings
- support ticket patterns
- user interviews
- qualitative feedback

---

### Developer

Provides access to system observability data.

Typical information:

- service latency
- error rates
- deployments
- system incidents

---

# Domain Separation

Each AI teammate only has access to their domain.

Example:

| Role          | Data Domain                        |
| ------------- | ---------------------------------- |
| Analyst       | product analytics                  |
| UX Researcher | user feedback and research         |
| Developer     | system performance and deployments |

Candidates must combine information from multiple roles to identify the root cause.

This prevents any single agent from revealing the answer directly.

---

# Free‑Form Investigation

Candidates interact with AI teammates using natural language questions.

Examples:

Show conversion funnel.

Break down checkout conversion by new users.

Were there any recent deployments affecting the payment service?

What feedback are users giving about checkout?

Each query must target a single domain.

If a query spans multiple domains, the system asks the candidate to split the question.

---

# Product Telemetry Model

SimWork scenarios simulate three types of product telemetry systems.

### Analytics

Product metrics and behavior data.

Examples:

- orders over time
- funnel conversion
- user segmentation

---

### Observability

Engineering system signals.

Examples:

- service latency
- error rates
- deployments

---

### User Signals

User experience feedback.

Examples:

- support tickets
- usability research
- user complaints

---

# Scenario Model

Each simulation scenario contains:

- product context
- problem statement
- underlying root cause
- realistic telemetry signals
- investigation clues

Candidates must discover the root cause by investigating signals across domains.

---

# Evaluation Philosophy

SimWork evaluates **how candidates think**, not just their final answer.

Signals evaluated include:

- investigation depth
- logical reasoning
- hypothesis formation
- ability to connect signals
- quality of proposed solutions

The system logs the candidate’s investigation path to support evaluation.

---

# Long‑Term Vision

SimWork aims to become a universal work simulation platform.

Future simulations may include:

- Product Management
- Engineering
- Design
- Data Analysis
- Operations
- Leadership

The platform's core principle remains the same:

Evaluate people by **simulating real work environments and observing how they operate**.
