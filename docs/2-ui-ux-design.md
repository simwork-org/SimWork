# UI/UX Design Specification

## AI Product Manager Simulation Interview (MVP)

---

# Overview

This document describes the user interface and interaction design for the **PM Simulation Interview web application**.

The platform allows candidates to investigate a simulated product problem by interacting with role‑based AI assistants and analyzing product data.

The UI should feel like a **lightweight product debugging workspace**, combining elements of:

- chat interface
- analytics dashboard
- interview environment

The experience should feel similar to:

- Slack (team conversation)
- Notion (structured workspace)
- Product analytics tools

The design must remain **minimal, focused, and immersive for problem solving**.

---

# Target User

Primary user: **Product Manager Candidate**

User goals:

- understand the problem
- investigate product signals
- ask questions to team members
- develop hypotheses
- test and refine hypotheses
- propose final solution

---

# Core UX Principles

### 1. Investigation First

The UI should guide the candidate toward **systematic investigation** rather than guessing.

### 2. Persistent Context

The problem statement should **always remain visible**.

### 3. Encourage Exploration

Candidates should feel comfortable asking many questions.

### 4. Realistic Team Interaction

Conversation with roles should feel like **talking to real colleagues**.

### 5. Clear Progression

The system must clearly guide the candidate through stages:

Problem → Investigation → Hypothesis → Refinement → Final Plan

---

# Visual Design System

## Color Theme

Dark professional workspace theme.

### Primary Background

#0F172A

### Secondary Panels

#1E293B

### Chat Background

#111827

### Primary Accent

#6366F1 (Indigo)

### Secondary Accent

#22C55E (Green)

### Warning Accent

#F59E0B (Amber)

### Text Colors

Primary Text  
#E5E7EB

Secondary Text  
#9CA3AF

---

# Typography

Primary Font  
Inter

Data Font  
JetBrains Mono

---

# Core Screens

---

# 1. Landing Page

Purpose: introduce the simulation.

### Elements

Header

- platform logo
- simulation name

Main Section

Simulation description example:

"You are the Product Manager for a food delivery platform.

Weekly orders have dropped by 18% over the past month.

Investigate the issue and propose a recovery plan."

Additional information

- estimated duration: 30 minutes
- short instructions

Primary CTA

Start Investigation

---

# 2. Investigation Workspace

Main simulation interface.

### Layout

---

## Problem Statement (persistent header)

| Team Panel | Investigation Chat | Data Panel |
| | | |
| Analyst | Conversation | Charts |
| UX | | Tables |
| Developer | | Metrics |

---

Hypothesis Panel + Final Submission

---

# Problem Statement Panel

Always visible.

Contains:

- problem summary
- investigation objective
- time remaining

Example:

Orders dropped by 18% in the last month.

Investigate the root cause and propose a recovery plan.

Time Remaining: 24 minutes

---

# Team Panel

Left sidebar listing available team roles.

### Roles

Data Analyst  
UX Researcher  
Developer

Each role contains:

- avatar
- description
- role color

Example:

Data Analyst  
Provides metrics, funnels, and segmentation data.

UX Researcher  
Provides usability insights and research findings.

Developer  
Provides system signals and deployment information.

---

# Role Avatars

To make conversations engaging, each role should have a visual avatar.

### Analyst

Color Accent: Blue  
Style: data scientist / analytics icon

### UX Researcher

Color Accent: Purple  
Style: research / design avatar

### Developer

Color Accent: Green  
Style: engineer avatar

Messages display:

Avatar + Role Name

Example:

[Avatar] Data Analyst  
Checkout → Payment conversion dropped from 22% to 14%.

---

# Investigation Chat

Central conversation interface.

Example interaction:

Candidate:
Show conversion funnel for the last 4 weeks.

Analyst:
Checkout → Payment conversion dropped significantly.

Week 1: 22%  
Week 2: 21%  
Week 3: 18%  
Week 4: 14%

Chat Features:

- role avatars
- timestamps
- scrollable history
- typing indicators

Example:

"Analyst is typing..."

---

# Data Panel

Right side panel displaying structured information.

### Funnel Visualization

App Open  
↓  
Product View  
↓  
Add to Cart  
↓  
Checkout  
↓  
Payment

### Metrics Table

Week 1: 52k orders  
Week 2: 51k  
Week 3: 47k  
Week 4: 42k

### Segment Breakdown

New Users: 9%  
Returning Users: 18%

Charts should be simple and readable.

---

# Hypothesis Panel

Candidate can propose hypotheses during investigation.

Prompt:

What do you believe might be causing the issue?

Input field.

Button:

Submit Hypothesis

---

# Hypothesis Lifecycle

The system allows hypothesis updates.

### States

Hypothesis Proposed  
Hypothesis Investigated  
Hypothesis Confirmed  
Hypothesis Rejected

Candidate actions:

Edit Hypothesis  
Replace Hypothesis  
Add Supporting Evidence

---

# Final Solution Submission

Final structured response.

### Fields

Root Cause  
Proposed Actions  
Prioritization Reasoning

Example actions:

- fix payment gateway latency
- add payment retry
- redesign payment UI

Submit button:

Submit Final Plan

---

# Completion Screen

Displayed after submission.

Example message:

Simulation completed successfully.

Your responses have been recorded for evaluation.

Optional message:

Thank you for participating.

---

# Interaction Enhancements

### Typing Indicators

Example:

Analyst is typing...

### Smart Suggestions

Optional suggestion chips:

Show funnel  
Break down by user type  
Check system deployments

### Query History

Candidate can scroll previous investigation queries.

---

# Device Support

Desktop-first design.

Recommended minimum width:

1280px

Mobile support not required for MVP.

---

# Data Logging (Hidden)

System should log:

- candidate queries
- investigation order
- roles consulted
- hypothesis changes
- time spent per step
- final submission

This data will be used for evaluation.

---

# Design Inspiration

Recommended references:

Notion  
Linear  
Stripe Dashboard  
Vercel Console

Goal: create a **focused and professional investigation workspace**.
