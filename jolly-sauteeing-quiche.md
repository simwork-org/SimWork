# Plan: 2 Scenarios with Shared Database

## Context

Restructure SimWork from a 3-challenge single scenario to **2 simple scenarios** sharing one database:

1. **Diagnostic** — "Checkout Conversion Drop": Orders are dropping, find the root cause and propose a fix. Delete the old promo_cliff/rupeeflow_v3/trust_erosion tier structure — replace with one clean scenario and one problem.
2. **Strategic** — "Premium Membership Launch": Design ZaikaNow Gold using the same data.

Both share `scenario.db`. Ground truth doc acts as the ideal solution for scoring.

---

## Step 1: Rewrite checkout_conversion_drop scenario_config.json

**File:** `scenarios/checkout_conversion_drop/scenario_config.json`

Strip out all 3 old problem entries. Replace with a clean single-problem config:

- `difficulty: "intermediate"` (not multi_tier)
- Add `scenario_type: "diagnostic"`, `icon: "trending_down"`
- `problems`: Single entry with:
  - `id: "order_drop_investigation"`
  - `challenge_title: "The Order Drop"`
  - `challenge_prompt`: "Completed orders have dropped across key metros since mid-January. Competitors are holding steady. Find what's causing the decline and propose a recovery plan."
  - `challenge_problem_statement`: Simple, focused framing about the order drop
  - `root_cause`: The RupeeFlow v3 UPI migration on Jan 10 broke payment confirmation handling, causing checkout failures concentrated on Android/UPI/metro users. A Feb 1 hotfix partially fixed it but trust damage persists.
  - `key_evidence`: Consolidated list of DB-verified evidence
  - `red_herrings_to_reject`: Keep the 5 red herrings
  - `tables_involved`: All relevant tables
  - `agents_required`: All 3 agents
- Simplify `evaluation_rubric` — keep 4 dimensions but frame for a single investigation
- Clean up `expected_investigation_path` and `expected_key_findings`
- Remove old challenge_title/challenge_prompt/challenge_problem_statement from deleted problems

---

## Step 2: Create premium_membership_launch scenario

**New directory:** `scenarios/premium_membership_launch/`

```
scenarios/premium_membership_launch/
├── scenario_config.json
├── reference.json
└── tables/
    └── scenario.db  → ../../checkout_conversion_drop/tables/scenario.db (symlink)
```

### scenario_config.json
- `scenario_id: "premium_membership_launch"`, `scenario_type: "strategic"`, `icon: "loyalty"`
- `problem_statement`: ZaikaNow exploring a premium tier "ZaikaNow Gold" — analyze customer segments, ordering patterns, satisfaction signals to design the membership and identify target users
- Single problem: `id: "gold_membership_design"`
- Agent personas: Same names (Priya/Kavya/Rohan) but context adapted for strategic analysis
- `agent_data_access`: Same tables, same access rules
- `evaluation_rubric`: Strategic dimensions (segmentation quality, pricing rationale, feature design, go-to-market)
- `expected_investigation_path`: segmentation → frequency → revenue → payment patterns → reviews → churn → feature design → pricing

### reference.json
- Same structure as checkout reference.json
- `mission_brief` reframed for strategic context
- `source_catalog`: Same tables (shared DB), descriptions lightly reframed
- `glossary`: Add ARPU, cohort LTV, power user, willingness-to-pay terms

---

## Step 3: Extend scenario list API

**File:** `backend/scenario_loader/loader.py`

Update `list_scenarios()` (line 21-28) to also return: `description` (from problem_statement), `scenario_type`, `industry`, `product`, `icon`.

**File:** `frontend/src/lib/api.ts`

Update `Scenario` interface to include: `description?`, `scenario_type?`, `icon?`

---

## Step 4: Rewrite landing page as scenario selector

**File:** `frontend/src/app/page.tsx`

- Remove hardcoded `SCENARIO_ID`
- On mount: `listScenarios()` then `getChallenges()` for each to get the single challenge_id
- 2 scenario cards (2-col desktop, stacked mobile)
- Each card: type badge, icon, title, description, "Begin" button
- Hero: "SimWork — Choose Your Scenario"

---

## Step 5: Update GROUND_TRUTH.md

**File:** `docs/GROUND_TRUTH.md`

Rewrite as the ideal solution reference for both scenarios. Crucially, each scenario must include **ideal investigation steps** — the sequence of queries/actions a strong candidate would take — so the scorer can evaluate the candidate's investigative process, not just their final answer.

### Scenario 1 — Checkout Conversion Drop (Diagnostic)

1. **Ideal Investigation Steps** (ordered sequence):
   - Step 1: Ask Analyst for daily order trends (Oct–Mar) — spot the volume decline pattern
   - Step 2: Ask Analyst to break down by city/platform — identify Android + primary metros as worst-hit
   - Step 3: Ask Analyst for checkout funnel breakdown pre/post Jan 10 — find the payment_attempt → order_complete break
   - Step 4: Ask Analyst to segment by payment method — isolate UPI as most affected
   - Step 5: Ask Engineering Lead for deployment timeline around Jan 10 — find DEP004 (RupeeFlow v3)
   - Step 6: Ask Engineering Lead for payment service latency/error trends — confirm p99 spike + error code shift
   - Step 7: Ask UX Researcher for support ticket themes — confirm upi_timeout and callback_delay complaints
   - Step 8: Ask UX Researcher for usability study findings — confirm 93% → 61% task completion drop
   - Step 9: (Strong candidate) Ask Analyst for post-hotfix cohort analysis — discover trust damage persists
   - Step 10: (Strong candidate) Ask UX Researcher for review sentiment — find "shifted to Swiggy" / "ordering less" themes
   - Each step builds on the prior one; red herrings should be identified and rejected along the way

2. **Root cause** with DB-verified evidence (deployment, latency, error codes, support tickets, usability data)

3. **Red herrings** and why each is wrong

4. **Ideal recovery plan**: Technical rollback/fix, payment-status UX improvements, trust recovery for affected cohorts, monitoring

5. **Evaluation rubric** with scoring for both process (did they follow a logical investigation path?) and outcome (did they reach the right conclusion?)

### Scenario 2 — Premium Membership Launch (Strategic)

1. **Ideal Investigation Steps** (ordered sequence):
   - Step 1: Ask Analyst for user segmentation overview (new/casual/returning/power breakdown)
   - Step 2: Ask Analyst for ordering frequency and ARPU by user_type — identify high-value segments
   - Step 3: Ask Analyst for platform and city distribution of power users — understand the target cohort
   - Step 4: Ask Analyst for payment method preferences by segment — inform premium checkout features
   - Step 5: Ask UX Researcher for review themes from power/returning users — find satisfaction drivers and pain points
   - Step 6: Ask UX Researcher for support ticket patterns by user_type — identify service gaps a premium tier could fill
   - Step 7: Ask Engineering Lead for service reliability data — inform premium SLA promises
   - Step 8: Synthesize: define target segment, feature set, pricing model, launch strategy

2. **Key signals** the candidate should find in the data

3. **Ideal membership design**: Target cohort definition, feature set, pricing rationale, launch strategy

4. **Evaluation rubric** with scoring for process and outcome

---

## Files Summary

| File | Action |
|------|--------|
| `scenarios/checkout_conversion_drop/scenario_config.json` | Rewrite — 1 problem, add scenario_type/icon |
| `scenarios/premium_membership_launch/scenario_config.json` | New |
| `scenarios/premium_membership_launch/reference.json` | New |
| `scenarios/premium_membership_launch/tables/scenario.db` | Symlink |
| `backend/scenario_loader/loader.py` | Extend list_scenarios() |
| `frontend/src/lib/api.ts` | Update Scenario interface |
| `frontend/src/app/page.tsx` | Rewrite as scenario selector |
| `docs/GROUND_TRUTH.md` | Rewrite for both scenarios |

**No changes needed:** db.py, routes.py, engine.py, router, scorer

---

## Verification

1. `GET /api/v1/scenarios` — returns 2 scenarios with metadata
2. `GET /api/v1/scenarios/checkout_conversion_drop/challenges` — returns 1 challenge
3. `GET /api/v1/scenarios/premium_membership_launch/challenges` — returns 1 challenge
4. Start session for each — workspace loads correct problem_statement
5. Landing page shows 2 scenario cards
6. Symlink works: queries against premium scenario return data
