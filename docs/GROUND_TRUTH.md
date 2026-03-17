# Ground Truth — SimWork Scenario Solutions

> **Internal evaluator reference.** Contains the ideal solution, investigation steps, and
> scoring rubric for each scenario. All figures verified against `scenarios/checkout_conversion_drop/tables/scenario.db`.

---

## Scenario 1: Checkout Conversion Drop (Diagnostic)

### Problem Statement

Completed orders have dropped across key Indian metros since mid-January while competitors hold steady. Find the root cause and propose a recovery plan.

### Root Cause

The RupeeFlow v3 payment migration (DEP004) on January 10, 2025 degraded UPI confirmation and callback handling. Android users in high-volume metros (Bengaluru, Mumbai, Delhi NCR) were hit hardest, causing payment failures, delayed confirmations, and order completion drops. A Feb 1 hotfix (DEP007) partially restored reliability, but behavioral trust damage persists among power and returning users who reduced ordering frequency.

### Data Integrity Notes

The dataset is fully reconciled — every cross-table relationship is consistent:

- Every order's `total_amount` equals `SUM(menu_items.price × order_items.quantity)`
- Every order's `session_id` exists in `funnel_events` (all sessions start with `app_open`)
- Users, restaurants, and drivers are city-matched within each order
- Reviews only exist for completed (delivered) orders
- Support tickets are always created after their referenced order
- Payment amounts match order totals; payment session_ids match order session_ids
- Order items reference menu items from the correct restaurant

### Ideal Investigation Steps

A strong candidate should follow this sequence, building each step on prior findings:

**Step 1 — Establish the baseline and decline pattern**
- Agent: Analyst
- Query: Daily order trends from Oct 2024 to Mar 2025
- Expected finding: Orders spike Dec 26--Jan 5 (promo period), normalize by Jan 7, then a separate sharper decline begins Jan 10
- Key insight: The Jan 10 drop is distinct from the post-promo normalization (3-day gap)

**Step 2 — Identify the funnel break**
- Agent: Analyst
- Query: Checkout funnel breakdown (app_open → restaurant_view → add_to_cart → checkout_start → payment_attempt → order_complete) before and after Jan 10. Every session starts at app_open; orders are the subset that complete all 6 steps.
- Expected finding: The largest break occurs at payment_attempt → order_complete
- Key insight: This is a payment-step problem, not a traffic or browsing problem

**Step 3 — Segment by city and platform**
- Agent: Analyst
- Query: Order completion rates by city and platform after Jan 10
- Expected finding: Android users in Bengaluru, Mumbai, Delhi NCR show the sharpest degradation
- Key insight: The problem is concentrated on specific platforms and geographies

**Step 4 — Isolate the payment method**
- Agent: Analyst
- Query: Payment failure rates by method (UPI, credit card, debit card, wallet, COD)
- Expected finding: UPI is the most affected method, credit card and COD relatively stable
- Key insight: This points to a UPI-specific infrastructure issue

**Step 5 — Find the deployment**
- Agent: Engineering Lead
- Query: Deployment timeline around Jan 10
- Expected finding: DEP004 on Jan 10: "Migrated to RupeeFlow v3 payment orchestration"
- Key insight: The migration aligns precisely with the payment failure onset

**Step 6 — Confirm the technical impact**
- Agent: Engineering Lead
- Query: Payment service latency and error rate trends
- Expected finding: p99 latency spikes from 503ms to 2,519ms on Jan 10, sustained 2,900--6,700ms through Jan. Error codes shift to UPI_CALLBACK_TIMEOUT, BANK_TIMEOUT, PAYMENT_PROVIDER_ERROR
- Key insight: Technical confirmation of the RupeeFlow v3 regression

**Step 7 — Validate with user feedback**
- Agent: UX Researcher
- Query: Support ticket themes since Jan 10
- Expected finding: Tickets dominated by upi_timeout and callback_delay categories, critical priority
- Key insight: User-facing impact confirms the technical findings

**Step 8 — Check usability research**
- Agent: UX Researcher
- Query: Usability study findings
- Expected finding: Task completion dropped from 93% (Nov baseline) to 61% (Jan study). Android worst at 49%
- Key insight: Independent research confirms the scale of degradation

**Step 9 — Assess post-fix recovery** (strong candidate)
- Agent: Analyst
- Query: Order volumes and completion rates in Feb (post-hotfix DEP007 on Feb 1)
- Expected finding: Technical metrics improve but total orders drop 19.0% (8,194 → 6,634). Platform mix shifts: Android 58.9% → 56.9%, web 21.6% → 24.3%
- Key insight: Technical fix worked but business impact persists — users migrating away

**Step 10 — Identify trust damage** (strong candidate)
- Agent: UX Researcher
- Query: Review sentiment from Feb onward
- Expected finding: 52 trust-damage reviews: "shifted to Swiggy," "ordering less," "don't trust the payment flow," "family orders twice a week instead of daily"
- Key insight: Behavioral trust damage persists beyond the technical fix

### Red Herrings

| Signal | Why It's Wrong |
|--------|---------------|
| New Year campaign spike (Dec 26--Jan 5) | Resolves by Jan 7. 3-day gap before payment failures start Jan 10. |
| Search service p99 spike (Jan 8) | Brief, resolves quickly, no correlation with checkout failures. |
| Republic Day promo (late Jan) | Merchandizing change, not payment infrastructure. |
| Notification service errors (Jan 20--22) | Communication channel, not payment flow. |
| Checkout success animation (Jan 10) | Cosmetic change, insufficient scale to explain the degradation. |

### DB-Verified Evidence

| Signal | Value |
|--------|-------|
| DEP004 deployment | 2025-01-10 06:00, "Migrated to RupeeFlow v3 payment orchestration" |
| Pre-incident completion | 84.6% (Jan 8--9) |
| Post-incident completion | 73.6% (Jan 10--15) |
| Failed orders per day | ~12 (baseline) → ~30 (post Jan 10), 2.4x increase |
| p99 latency | 503ms → 2,519ms on Jan 10, sustained 2,900--6,700ms |
| Usability task completion | 93% (Nov) → 61% (Jan), Android 49% |
| Post-hotfix order volume | Jan: 8,194 → Feb: 6,634 (19.0% drop) |
| Android share shift | 58.9% (Jan) → 56.9% (Feb) |
| Web share shift | 21.6% (Jan) → 24.3% (Feb) |
| Trust damage reviews | 52 reviews (Feb--Mar) with competitor-switching themes |

### Ideal Recovery Plan

1. **Immediate (P0):** Roll back or hot-patch RupeeFlow v3 UPI callback handling. Monitor p99 latency and UPI success rate in real-time.
2. **Short-term (P1):** Improve payment status UX — show clear confirmation/failure states, add retry with status tracking, eliminate "money debited but no order" uncertainty.
3. **Medium-term (P1):** Trust recovery for affected cohorts — targeted communication to power/returning Android users in primary metros, offer goodwill credits, proactive order confirmation notifications.
4. **Monitoring:** Track repeat-order frequency among affected cohorts (power/returning + Android + primary metros) as the key recovery metric. Technical p99 alone is insufficient.

### Evaluation Rubric

| Dimension | Weight | Excellent | Good | Adequate | Poor |
|-----------|--------|-----------|------|----------|------|
| Root Cause Identification | 35% | Identifies RupeeFlow v3 migration, explains UPI regression, links to Android-metro impact, recognizes trust damage | Identifies payment gateway + UPI/city, but may miss trust damage | Identifies payment step as problem, doesn't isolate migration | Blames promos, search, or traffic |
| Investigation Process | 25% | Queries all 3 agents, cross-references evidence, rejects red herrings, builds coherent timeline | Uses multiple agents, connects main evidence | Explores some evidence, misses links | Single agent, weak evidence |
| Solution Quality | 25% | Technical fix + UX improvements + trust recovery + monitoring | Technical fix + some recovery actions | Fixes payment reliability only | Generic actions |
| Communication | 15% | Frames for leadership with impact, segments, trust risk, recovery narrative | Clear summary with evidence | Explains issue with limited synthesis | Fragmented observations |

---

## Scenario 2: Premium Membership Launch (Strategic)

### Problem Statement

ZaikaNow is exploring a premium membership tier — "ZaikaNow Gold" — to boost retention and revenue. Analyze the customer base, ordering patterns, and satisfaction signals to design the membership offering.

### Ideal Investigation Steps

**Step 1 — Understand user segmentation**
- Agent: Analyst
- Query: User count and distribution by user_type (new, casual, returning, power)
- Expected finding: Clear segmentation exists — power users are a small but high-value group, casual users are the largest segment
- Key insight: Natural target for premium tier is power + returning users

**Step 2 — Analyze ordering frequency and revenue by segment**
- Agent: Analyst
- Query: Average orders per user and ARPU by user_type
- Expected finding: Power users order 4--5x more frequently than casual users and have significantly higher ARPU
- Key insight: Power users generate disproportionate revenue — high willingness-to-pay signal

**Step 3 — Map the geographic and platform profile of high-value users**
- Agent: Analyst
- Query: Distribution of power/returning users by city and platform
- Expected finding: Android dominant (~62%), concentrated in Bengaluru, Mumbai, Delhi NCR
- Key insight: Mobile-first, metro-focused membership experience

**Step 4 — Understand payment preferences by segment**
- Agent: Analyst
- Query: Payment method distribution by user_type
- Expected finding: UPI dominates among frequent orderers; power users have highest transaction volumes
- Key insight: Payment reliability is a key value proposition for premium — "guaranteed checkout"

**Step 5 — Extract satisfaction drivers from reviews**
- Agent: UX Researcher
- Query: Review themes from power and returning users (ratings, common praise/complaints)
- Expected finding: High-value users praise restaurant quality and delivery speed, complain about payment reliability and order accuracy
- Key insight: Premium features should address: payment reliability, delivery guarantees, restaurant curation

**Step 6 — Identify service gaps from support tickets**
- Agent: UX Researcher
- Query: Support ticket categories and frequency by user_type
- Expected finding: High-value users file more tickets about payment issues and delivery delays
- Key insight: Premium SLA opportunities: priority support, guaranteed refund windows

**Step 7 — Assess platform reliability for SLA promises**
- Agent: Engineering Lead
- Query: Service metrics baseline — payment service latency, error rates, uptime
- Expected finding: Payment service has known reliability issues (p99 spikes), other services more stable
- Key insight: Premium tier must include priority payment routing or redundancy to deliver on SLA promises

**Step 8 — Synthesize the membership design**
- All findings combined into: target segment definition, feature set, pricing model, launch strategy

### Ideal Membership Design

**Target Segment:** Power and returning users on Android in primary metros (Bengaluru, Mumbai, Delhi NCR) — they represent the highest ordering frequency, ARPU, and engagement.

**Feature Set:**
- Priority checkout with guaranteed payment confirmation (reduced UPI timeout risk)
- Free delivery on orders above a threshold
- Exclusive restaurant access or early access to new restaurants
- Priority customer support with faster resolution SLA
- Order accuracy guarantee with instant refund

**Pricing Rationale:** Based on ARPU analysis — if power users spend ~INR 2,000--3,000/month, a membership at INR 149--199/month (5--10% of monthly spend) offers clear value through delivery savings and reliability guarantees. The break-even point should be 2--3 orders/month with free delivery.

**Launch Strategy:** Start with power users in Bengaluru (highest concentration), invite-only beta to create exclusivity, measure retention lift and ordering frequency change, then expand to Mumbai and Delhi NCR.

### Evaluation Rubric

| Dimension | Weight | Excellent | Good | Adequate | Poor |
|-----------|--------|-----------|------|----------|------|
| Segmentation Quality | 30% | Data-backed cohort definition with specific sizes, ARPU, frequency, and behavioral patterns | Identifies high-value segments but lacks precision | Recognizes user types exist but doesn't quantify | Generic targeting |
| Feature Design | 25% | Features tied to identified pain points and satisfaction drivers with evidence from reviews/tickets | Reasonable features with some data connection | Generic membership features | No data linkage |
| Pricing Rationale | 20% | Pricing backed by ARPU analysis, ordering frequency, and willingness-to-pay math | Reasonable pricing with some data support | Price point without justification | No pricing or arbitrary |
| Investigation Process | 25% | Queries multiple agents, builds from segmentation to recommendation, uses quant + qual evidence | Uses multiple agents, coherent analysis | Some data exploration, misses key dimensions | Shallow, single agent |

---

## Database Reference

Both scenarios share `scenarios/checkout_conversion_drop/tables/scenario.db`:

- ~48,754 orders across Oct 2024 -- Mar 2025
- 15 tables: users, orders, payments, restaurants, menu_items, order_items, drivers, funnel_events, reviews, support_tickets, ux_changelog, deployments, service_metrics, error_log, documents
- MECE schema: city, platform, user_type in users table only; other tables reference via FK
- Fully reconciled: order totals = item prices × quantities, city-matched users/restaurants/drivers, all orders linked to funnel sessions, reviews only on completed orders, tickets created after their order
