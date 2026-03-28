# Ideal Investigation Path — Checkout Conversion Drop

## Scenario Brief

ZaikaNow (food delivery) has seen a significant drop in completed orders starting mid-January across key Indian metros. Competitors are holding steady. The candidate must find the root cause using three agents (Data Analyst, UX Researcher, Engineering Lead) and propose a recovery plan.

## Key Dates

| Date | Event |
|------|-------|
| Oct 1, 2024 | Data starts |
| Dec 26, 2024 – Jan 5, 2025 | New Year promo (RED HERRING) |
| Jan 10, 2025 | RupeeFlow v3 migration (ROOT CAUSE) |
| Feb 1, 2025 | Hotfix deployed (partial recovery) |
| Feb 16, 2025 | Trust damage visible in power/returning users |
| Mar 31, 2025 | Data ends |

## Available Agents

- **Data Analyst** — orders, payments, funnel_events, users, restaurants, menu_items, drivers
- **Engineering Lead** — deployments, service_metrics, error_log, system_architecture.md
- **UX Researcher** — reviews, support_tickets, ux_changelog, usability_study.md

---

## Step-by-Step Investigation

### Step 1: Understand the overall trend
**Agent:** Data Analyst
**Question:** "Show me daily completed orders over the full available period"

**What you'll see:** Steady orders Oct–Dec (~280-320/day), a spike during New Year promo (Dec 26–Jan 5), then a SHARP drop from ~283 to 166 on Jan 10 that never fully recovers.

> **SAVE TO BOARD**
> **Note:** "Daily orders drop 40% on Jan 10 — from ~283 to 166. This is NOT the promo normalization (which ended Jan 5). Something specific broke on Jan 10."

---

### Step 2: Identify WHERE in the funnel users are dropping
**Agent:** Data Analyst
**Question:** "Compare the checkout funnel before and after Jan 10 — show me sessions by event type for Jan 5-9 vs Jan 10-15"

**What you'll see:** All top-of-funnel stages (app_open, restaurant_view, add_to_cart, checkout_start) are actually HIGHER after Jan 10. But order_complete drops from 1,577 to 1,441 despite payment_attempts increasing from 1,695 to 1,898.

> **SAVE TO BOARD**
> **Note:** "Traffic is UP after Jan 10 but order completions are DOWN. The break is specifically at payment_attempt → order_complete. This is a payment completion problem, not a traffic or discovery issue."

---

### Step 3: Check payment success rate by payment method
**Agent:** Data Analyst
**Question:** "Show me payment success rate by payment method, before vs after Jan 10"

**What you'll see:** UPI drops from 82.2% to 53.1% (29-point drop). Other methods also drop but less severely: credit_card 78% → 66%, debit_card 82% → 63%, wallet 78% → 61%. UPI is the dominant payment method (~60% of transactions), making it the primary driver.

> **SAVE TO BOARD**
> **Note:** "UPI is hit hardest — 29-point drop in success rate (82% → 53%). Other methods degrade ~15 points. Since UPI is 60%+ of transactions, this is the main driver of the order drop."

---

### Step 4: Check what happened on Jan 10 — deployments
**Agent:** Engineering Lead
**Question:** "What deployments happened around Jan 8 to Jan 12?"

**What you'll see:** DEP004 — RupeeFlow v3 payment gateway migration deployed on Jan 10 at 06:00.

> **SAVE TO BOARD**
> **Note:** "DEP004: RupeeFlow v3 migration deployed Jan 10 at 06:00. This is the exact date and time the payment success rate crashed. The payment gateway was changed from v2 to v3."

---

### Step 5: Check payment service health metrics
**Agent:** Engineering Lead
**Question:** "Show me payment service p99 latency and error rate from Jan 8 to Jan 14"

**What you'll see:** p99 latency spikes from ~495ms to ~2,421ms on Jan 10 (5x increase), climbing to 3,481ms by Jan 14. Error rate jumps from 0.4% to 3.2%+.

> **SAVE TO BOARD**
> **Note:** "Payment service p99 latency spiked 5x (495ms → 2,421ms) on Jan 10 — the exact day of the RupeeFlow v3 migration. Error rate jumped 8x. This confirms the migration degraded payment processing."

---

### Step 6: Check error patterns
**Agent:** Engineering Lead
**Question:** "Show me the top error codes from Jan 10 to Jan 15"

**What you'll see:** PAYMENT_PROVIDER_ERROR (362), UPI_CALLBACK_TIMEOUT (156), UPI_COLLECT_PENDING (86), TRANSACTION_REVERSED (84), BANK_TIMEOUT (52). Three of the top 5 are UPI-specific.

**Note:** Corroborates findings — 3 of 5 top errors are UPI-specific, confirming UPI callback handling broke in the v3 migration.

---

### Step 7: Check the usability study
**Agent:** UX Researcher
**Question:** "Show me the usability study findings"

**What you'll see:** Task completion dropped from 93% to 61%. Android worst at 49%. Users report money debited without confirmation. Trust damage persists even after successful retries.

> **SAVE TO BOARD**
> **Note:** "Usability study confirms user-facing impact: task completion 93% → 61%. Key finding: even after successful retries, users report reduced willingness to order again — trust damage is real and persists beyond the technical fix."

---

### Step 8: Check support tickets
**Agent:** UX Researcher
**Question:** "Show me support ticket categories from Jan 5 to Jan 20"

**What you'll see:** Spike in payment-related tickets. Volume is low relative to the scale of failures, suggesting most users don't file tickets — they just leave.

**Note:** Don't save — low volume makes this weak evidence. The usability study is the stronger qualitative signal.

---

### Step 9: Check post-hotfix recovery
**Agent:** Data Analyst
**Question:** "Show me daily completed orders from Jan 10 to Mar 15"

**What you'll see:** After Feb 1 hotfix, completed orders improve from ~178 to ~224-236, but never return to the pre-Jan-10 baseline of ~280-320. Gap persists through March.

**Note:** Optional save. The partial recovery confirms the hotfix helped technically, but the persistent gap confirms trust damage — users who experienced failures are ordering less or have switched.

---

### Step 10: Check UPI recovery across phases
**Agent:** Data Analyst
**Question:** "Show me UPI payment success rate across the full timeline — monthly or by phase"

**What you'll see:** UPI: 80.9% (baseline) → 53.0% (incident) → 67.3% (partial recovery) → 73.5% (trust damage). UPI never returns to 80.9% baseline, stalling at 73.5%.

**Note:** Optional save. Shows the technical recovery is incomplete — UPI success rate improved but plateaued ~7 points below baseline.

---

## Evidence Board Summary (5 items to save)

| # | Title | Why it matters |
|---|-------|---------------|
| 1 | Daily Orders Trend | Shows the Jan 10 break point — sharp 40% drop, not promo-related |
| 2 | Funnel Break at Payment Step | Traffic is UP but completions DOWN — isolates the problem to payment |
| 3 | UPI Success Rate Drop | UPI drops 29 points vs ~15 for other methods — identifies the affected method |
| 4 | DEP004: RupeeFlow v3 Migration | The root cause — deployment on Jan 10 at 06:00 |
| 5 | Payment Service Latency Spike | Technical confirmation — 5x latency increase, 8x error rate |

Optional 6th item: Trust damage from usability study (task completion 93% → 61%, users switching to competitors)

---

## Red Herrings to Recognize and Dismiss

| Signal | Why it's NOT the cause |
|--------|----------------------|
| New Year promo ending (Jan 5) | Promo normalization resolves by Jan 7. The payment drop starts Jan 10 — 3-day gap. Different cause. |
| Search service p99 spike (Jan 8) | Brief, resolves immediately. Unrelated to checkout/payment flow. |
| Republic Day promo (late Jan) | Merchandizing change, not payment infrastructure. |
| Notification service errors (Jan 20-22) | Communication channel issue, not payment authorization. |
| Checkout success animation (Jan 10) | Cosmetic change, too minor to explain the scale of the problem. |

---

## Root Cause Summary

**What:** The RupeeFlow v3 payment gateway migration (DEP004) deployed on January 10, 2025 broke UPI callback confirmation handling and degraded overall payment processing.

**Who's affected:** All users, but UPI payment users hit hardest (29-point success rate drop vs ~15 for other methods). UPI represents 60%+ of all transactions.

**Impact:** Completed orders dropped 40% on Jan 10. UPI success rate dropped from 82% to 53%. Payment service p99 latency increased 5x. Trust damage persists — even after Feb 1 hotfix, order volumes remain 25-30% below baseline.

**Recovery plan:**
1. **Immediate:** Roll back to RupeeFlow v2 or fix v3 UPI callback handling
2. **UX:** Add clear payment status messaging, retry guidance, and pending-payment reassurance
3. **Trust recovery:** Targeted outreach to affected users (UPI payers in top metros) with credits/guarantees
4. **Monitoring:** Track UPI success rate and repeat-order rate as recovery KPIs

---

## Scoring Dimensions

| Dimension (Weight) | What "excellent" looks like |
|--------------------|---------------------------|
| Root Cause Identification (35%) | Identifies RupeeFlow v3 migration, explains UPI as primary affected method, links to payment service degradation, recognizes post-fix trust damage |
| Investigation Methodology (25%) | Uses all 3 agents, cross-references evidence across domains, rejects red herrings with reasoning, builds coherent timeline |
| Solution Quality (25%) | Proposes stabilization + UX fixes + trust recovery for affected users + monitoring |
| Communication (15%) | Frames for leadership with business impact, affected segments, trust risk, and recovery narrative |
