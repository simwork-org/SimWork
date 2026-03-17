# Plan: 3 SimWork Improvements (separate branches)

**Context**: Improve SimWork's realism and agent quality in 3 independent branches: expand scenario data, make agents iterative with real skills, and add agent intro messages replacing skill hints.

## Sequencing
1. **`feature/realistic-scenario-data`** — first, since Items 2 & 3 reference data sources
2. **`feature/iterative-agents`** — second, depends on new data file names/columns
3. **`feature/agent-intro-messages`** — third (frontend-only, references skill/source names)

---

## Item 1: Expand Scenario Data (`feature/realistic-scenario-data`)

**Files to modify** — all under `scenarios/checkout_conversion_drop/`:

### analytics/metrics_timeseries.csv
- **Current**: 4 weekly rows, 4 columns
- **New**: ~48 daily rows (Dec 15 – Jan 31), add columns: `dau`, `revenue_usd`, `avg_order_value`, `sessions`, `bounce_rate`
- Baseline (Dec 15–Jan 9): ~7,200-7,800 orders/day, conversion ~0.21-0.23
- Red herring: Holiday promo Dec 26-31 bumps DAU ~12%
- Degradation (Jan 10+): Orders drop to ~6,000/day by Jan 31, conversion drops to 0.14
- Add daily noise ±3-5%, weekend dips, one Saturday spike

### analytics/funnel_metrics.csv
- **Current**: 6 steps, single snapshot
- **New**: 6 steps × 7 weekly snapshots (Dec 15 – Jan 26)
- Columns: `week_start`, `step`, `users`, `conversion_rate_from_previous`, `cumulative_conversion`
- Key signal: `payment → order_success` drops from 95% to 61% post-Jan 10

### analytics/segments.csv
- **Current**: 7 rows, no time dimension
- **New**: ~20 rows with columns: `segment`, `segment_type`, `platform`, `week_start`, `checkout_conversion`, `orders`, `orders_change_pct_vs_baseline`
- Add segment types: platform, user_type, payment_method, region
- Key signals: iOS -30%, Apple Pay -40%, new users -25%
- Red herring: EU -15% partly from holiday calendar

### observability/service_latency.csv
- **Current**: 4 services × 4 weeks, latency 1-7ms (unrealistic)
- **New**: 6 services × ~48 daily rows, realistic values
- Columns: `date`, `service`, `p50_ms`, `p95_ms`, `p99_ms`, `request_count`
- Baseline payment_service: p50 ~120ms, p95 ~280ms, p99 ~450ms
- Post Jan 10: p50 → 600ms, p99 → 4,500ms
- Red herring: search_service p99 spike Jan 8 (index rebuild, resolves Jan 9)

### observability/error_rates.csv
- **Current**: 4 services × 4 weeks, clean monotonic increase
- **New**: 6 services × ~48 daily rows
- Columns: `date`, `service`, `error_rate_pct`, `error_count`, `total_requests`, `top_error_code`
- Payment errors spike from 0.3% → 5.8%, top codes shift to `GATEWAY_TIMEOUT` / `PAYMENT_PROVIDER_ERROR`
- Non-monotonic: brief dip Jan 14 (hotfix attempt, then regressed)
- Red herring: notification_service 0.8% errors Jan 20-22

### observability/deployments.json
- **Current**: 3 entries
- **New**: 12-15 entries (Dec 15 – Jan 31)
- Add fields: `deploy_id`, `time`, `author`, `commit_hash`
- Key entries: Jan 10 PayStream v3 migration (root cause), Jan 14 timeout hotfix, Jan 20 retry logic
- Many unrelated deploys as noise

### user_signals/user_feedback.csv
- **Current**: 13 rows, almost all payment/iOS
- **New**: 45-50 rows (Dec 20 – Jan 28)
- Columns: `date`, `feedback`, `rating`, `platform`, `user_segment`
- Pre Jan 10: positive reviews (4-5 stars), one search complaint (red herring)
- Post Jan 10: flood of payment complaints, overwhelmingly iOS, some unrelated noise ("delivery late", "wrong order")

### user_signals/support_tickets.csv
- **Current**: 11 rows
- **New**: 35-40 tickets (Dec 20 – Jan 28)
- Columns: `ticket_id`, `date`, `category`, `subcategory`, `issue`, `platform`, `priority`, `status`, `resolution_time_hours`
- Pre Jan 10: normal mix (delivery, account, UI bugs)
- Post Jan 10: dominated by payment/iOS, long resolution times (48-72hrs unresolved)
- Red herrings: promo code bug, address update issue

### user_signals/usability_findings.md
- Expand to n=20 participants, add December baseline study comparison
- Add quantitative: task completion 92% → 54%, avg time 3.2s → 12.8s
- Add "Workarounds Observed" and "Platform Comparison" sections

Root cause narrative preserved: PayStream v3 (Jan 10) → payment latency/errors → iOS worst hit → checkout conversion drops.

---

### Investigation Journey: Hidden Clues & Expected Candidate Path

The data is designed so a strong PM candidate discovers the root cause through cross-referencing multiple agents' domains. Here's the intended journey:

#### Phase 1: Spot the problem (Data Analyst)

**Hidden clue in metrics_timeseries.csv**: Orders decline starts Jan 10, but DAU stays relatively flat. This tells a sharp candidate: *users are still showing up, they just can't complete orders*. A weak candidate might blame "fewer users" — the data disproves that.

**Hidden clue in funnel_metrics.csv**: The `payment → order_success` step is the only one that degrades significantly (95% → 61%). All earlier funnel steps (browse, cart, checkout) are stable. This isolates the problem to the payment step specifically. A strong candidate asks: "Why is payment failing?"

**Hidden clue in segments.csv**: iOS is hit 6x worse than Android (-30% vs -5%). Apple Pay is devastated (-40%). Credit card on Android is fine. This is the *platform signal* — not a general payment issue, but something specific to the iOS payment path. A strong candidate notices the iOS/Android divergence and hypothesizes a platform-specific technical issue.

**Red herring**: The Dec 26-31 holiday promo DAU spike might mislead a candidate into thinking "traffic dropped after promo ended." But the timeline doesn't match — the real drop starts Jan 10, not Jan 1. A good PM separates correlation from causation.

**Red herring**: EU region shows -15% which could be mistakenly attributed to payment issues alone, but is partly a holiday calendar effect (different holiday patterns in EU). Tests if candidate considers multiple explanations.

#### Phase 2: Find the technical trigger (Developer)

**Hidden clue in deployments.json**: The PayStream v3 migration on Jan 10 lines up exactly with when metrics started declining. A strong candidate connects the dots: "Was there a deployment around Jan 10?" → finds the payment service migration.

**Hidden clue in service_latency.csv**: Only payment_service degrades. p99 goes from 450ms → 4,500ms (10x). All other services are stable. This confirms the payment service is the culprit, not a broader infrastructure issue.

**Hidden clue in error_rates.csv**: Error codes shift from generic `500` to `GATEWAY_TIMEOUT` and `PAYMENT_PROVIDER_ERROR`. This tells a technical PM: the issue is with the external payment provider integration, not internal code. The Jan 14 hotfix (timeout increase) briefly helped then regressed — showing the team tried but the fix was insufficient.

**Red herring**: search_service had a p99 spike on Jan 8 (before the payment issue). A candidate might chase this, but it resolved by Jan 9 and doesn't correlate with the Jan 10+ decline.

**Red herring**: notification_service errors Jan 20-22 are unrelated (email provider issue). Tests if candidate stays focused on the payment thread or gets distracted.

#### Phase 3: Validate with user voice (UX Researcher)

**Hidden clue in user_feedback.csv**: iOS users specifically mention "payment hangs," "times out," "had to switch to competitor." Android users are posting positive reviews in the same period. This is the qualitative confirmation of the platform-specific hypothesis.

**Hidden clue in support_tickets.csv**: Payment tickets are high/critical priority and have long resolution times (48-72hrs, many unresolved). The subcategories (`timeout`, `retry_unavailable`, `generic_error`) map directly to the technical findings. A strong candidate synthesizes: "Users are timing out because p99 latency is 4.5s, and the error message is unhelpful because it's a generic 500."

**Hidden clue in usability_findings.md**: Task completion rate went from 92% → 54%. Average payment time went from 3.2s → 12.8s. The "Workarounds Observed" section reveals users are switching to Android or PayPal — this shows the impact is driving real churn, not just frustration.

**Red herring**: A few support tickets about "promo code not working" and "delivery late" — normal operational noise that shouldn't distract from the payment pattern.

#### The "Aha" Moment

A strong candidate connects all three domains:
1. **Analytics**: Payment step conversion crashed, iOS/Apple Pay worst hit
2. **Engineering**: PayStream v3 deployed Jan 10, payment latency 10x'd, errors shifted to gateway timeouts
3. **User signals**: iOS users reporting payment failures, switching to competitors

Root cause: **The PayStream v3 migration introduced a latency regression in the iOS payment path, causing timeouts and failures that disproportionately affect iOS and Apple Pay users.**

### What a Strong PM Candidate Should Propose

After identifying the root cause, the candidate submits a solution. Here's what distinguishes good vs. great:

#### Minimum viable (passing):
- **Root cause identified**: PayStream v3 migration caused payment service latency spike
- **Immediate action**: Roll back to PayStream v2 (rollback_available: true in deployment data)

#### Strong (above average):
- **Structured root cause**: Links deployment date, latency data, iOS-specific impact, and user feedback
- **Tiered action plan**:
  1. **Immediate (0-24h)**: Roll back PayStream v3 on iOS; keep v3 on Android where it works fine
  2. **Short-term (1-2 weeks)**: Work with PayStream on the iOS SDK issue; improve error messages from generic "Something went wrong" to specific "Payment is taking longer than usual, please retry"
  3. **Medium-term (1 month)**: Add payment retry mechanism (users flagged this in tickets); implement circuit breaker pattern; add payment-specific monitoring alerts

#### Excellent (PM star):
All of the above, plus:
- **User recovery plan**: Proactive outreach to churned iOS users (the ones who said "switched to competitor") with a "we fixed it" message + incentive
- **Process improvement**: Proposes canary deployments for payment-critical services — "We should have caught this on 5% of traffic before rolling to 100%"
- **Monitoring gaps identified**: "We had no alert when p99 latency crossed 1s on payment. Add SLO-based alerting for payment completion rate"
- **Data-backed prioritization**: Uses the segment data to quantify impact — "iOS represents X% of revenue, the payment failure rate of 39% means we lost approximately Y orders/day, ~$Z revenue impact"
- **Stakeholder communication**: Frames the solution in terms leadership cares about — revenue recovery timeline, competitive risk (users switching), and prevention plan

### Update to scenario_config.json

Expand the config to include the evaluation rubric:
- Add `evaluation_rubric` with scoring criteria for root_cause_identification, investigation_methodology, solution_quality, and communication
- Add `expected_key_findings` listing the critical data points a candidate should discover
- Add `red_herrings` listing the distractors and why they don't explain the issue

---

## Item 2: Iterative Agents with Skills (`feature/iterative-agents`)

### backend/telemetry_layer/telemetry.py — Add granular data access

Add new constant `AGENT_SKILLS`:
```python
AGENT_SKILLS = {
    "analyst": {
        "sources": ["metrics_timeseries.csv", "funnel_metrics.csv", "segments.csv"],
        "skills": [
            {"name": "query_timeseries", "description": "Query daily order metrics, conversion rates, DAU, revenue", "source": "metrics_timeseries.csv"},
            {"name": "query_funnel", "description": "Query checkout funnel conversion by week", "source": "funnel_metrics.csv"},
            {"name": "query_segments", "description": "Query conversion by segment (platform, user type, etc.)", "source": "segments.csv"},
        ]
    },
    # similar for developer (latency, errors, deployments) and ux_researcher (feedback, tickets, usability)
}
```

Add new functions:
- `list_available_sources(scenario_id, agent)` → returns filenames for agent's domain
- `query_source(scenario_id, agent, source, filters=None)` → loads specific file, applies optional filters (date_range, columns, service, segment, limit). Returns `{"source": name, "rows": [...], "row_count": N}`

### backend/agent_router/router.py — 2-step routing

Replace single `route_query()` with 3-step flow:

1. **`_select_skills(llm, agent, query, history)`** — LLM call #1: given available skills list, agent picks 1-2 skills + filters to answer the question. Returns JSON `{"skills": [{"name": ..., "filters": {...}}]}`

2. **`_execute_skills(scenario_id, agent, selections)`** — No LLM: calls `telemetry.query_source()` for each selected skill, collects results into formatted `data_context` string

3. **`_formulate_response(llm, agent, query, data_context, history)`** — LLM call #2: given the fetched data slice + response schema, formulate the structured JSON response (insight + chart + next_steps)

**Fallback**: If Step 1 fails to parse, fall back to current behavior (load all domain data, single LLM call).

API contract unchanged — frontend sees same `{agent, response, chart, next_steps}`.

### No changes to: engine.py, api/routes.py, frontend

---

## Item 3: Agent Introduction Messages (`feature/agent-intro-messages`)

### frontend/src/app/workspace/[sessionId]/page.tsx

1. **Add `AGENT_INTROS` constant** — Per-agent intro message referencing their actual data sources and skills. E.g.: "Hello! I'm the Data Analyst. I have access to: metrics_timeseries (daily orders, conversion, DAU, revenue), funnel_metrics (weekly funnel breakdown), segments (by platform, user type, payment method). I can help with trend analysis, funnel deep-dives, and segment comparisons. What would you like to investigate?"

2. **Remove skill badges from team panel** — Delete the `{isSelected && (...skills.map...)}` block in the agent buttons

3. **Inject intro on agent selection** — When clicking an agent, push an intro message into `messages` state (role: "agent", agent: id, content: intro text). Track shown intros with `introShown` Set state to prevent duplicates.

4. **Show default agent intro on mount** — `useEffect` on mount injects analyst's intro as first message

5. **Remove/update empty state** — The "Select a teammate..." placeholder is no longer needed since analyst intro shows immediately

---

## Verification

- Item 1: Data files are valid CSV/JSON/MD, `cd backend && python -c "from telemetry_layer.telemetry import get_telemetry_for_agent; print(get_telemetry_for_agent('checkout_conversion_drop', 'analyst'))"`
- Item 2: `cd backend && python -c "from agent_router.router import route_query; from llm_interface.llm_client import LLMClient; ..."`
- Item 3: `cd frontend && npx next build`
