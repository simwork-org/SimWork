# SimWork Backlog

> Three workstreams to make SimWork deployment-ready. Work top-to-bottom within each workstream.

---

## Ground Truth: Three Embedded Problems

### Problem 1 — Easy: "Promo Cliff"

- **Root Cause**: New Year campaign (Dec 26 – Jan 5) drove a ~25% order spike. When it ended, volume normalized. Looks like a "drop" if you only check top-line orders.
- **Discovery Path**: Single agent (Analyst). Compare daily order trends against ux_changelog campaign dates. Signal is in one table with a simple time-series query.
- **Key Evidence**: (1) Orders spike Dec 26 – Jan 5, return to baseline by Jan 7. (2) ux_changelog: "New Year offer rail" on Dec 27. (3) Upper-funnel sessions also normalize — demand-side, not failure-side.
- **Trap**: Weak candidate stops here and blames the promo ending for the Jan 10+ payment degradation. Strong candidate notices the 3-day gap (promo normalizes Jan 7, payment failures start Jan 10).

### Problem 2 — Medium: "RupeeFlow v3 UPI Migration"

- **Root Cause**: RupeeFlow v3 migration on Jan 10 degraded UPI confirmation/callback handling. Android users in Bengaluru, Mumbai, Delhi NCR hit hardest.
- **Discovery Path**: Requires 2–3 agents. Analyst isolates payment-step funnel break + Android/metro/UPI segment. Engineering Lead finds deployment timeline + latency spike. UX Researcher confirms with support tickets + usability study.
- **Key Evidence**: (1) Funnel break at payment_attempt → order_complete after Jan 10. (2) UPI most affected, Android + primary metros worst segment. (3) DEP004 "Migrated to RupeeFlow v3" on Jan 10. (4) Payment service p99 spikes 470ms → 2600ms+. (5) Error codes shift to UPI_CALLBACK_TIMEOUT. (6) Support tickets dominated by "upi_timeout." (7) Usability study: task completion 93% → 61%.
- **Red Herrings to Reject**: Promo normalization, search service p99 spike (Jan 8), Republic Day promo, notification errors (Jan 20–22), checkout animation (Jan 10).

### Problem 3 — Hard: "Trust Erosion Cascade"

- **Root Cause**: After Feb 1 hotfix, payment metrics improved but power/returning users on Android in primary metros still order less. Behavioral trust damage — not technical failure.
- **Discovery Path**: All three agents + cohort reasoning. Analyst segments by user_type + time phase (power/returning users show elevated cancellation, fewer orders). Engineering confirms technical recovery. UX Researcher surfaces trust themes from reviews ("ordering less," "switched to Swiggy").
- **Key Evidence**: (1) Order volume from affected cohort drops ~20% in trust phase despite technical fix. (2) Platform mix shifts: Android share 62% → 56%, web 20% → 26%. (3) Power/returning Android users: 14–15% cancellation vs 10% baseline. (4) Reviews: "don't trust the payment flow," "shifted to Swiggy." (5) Funnel: returning/power Android users browse less (restaurant_view 70% vs 77% baseline). (6) Usability study recommends tracking repeat-order drop.
- **Why Hard**: Technical metrics look recovered. Signal is in behavioral/cohort data requiring user_type segmentation + temporal phase analysis + qualitative trust themes. Must reason about second-order effects.

---

## WS1: Data — Clean Schema + Three Problems

> Status: **In Progress**

- [x] WS1-01: Design MECE schema (platform/city only in users, FKs explicit)
- [ ] WS1-02: Rewrite generate_data.py with clean schema + 50K scale
- [ ] WS1-03: Embed Easy problem signals (promo spike 25%, clean gap before Jan 10)
- [ ] WS1-04: Strengthen Hard problem signals (cohort order frequency drop, trust reviews)
- [ ] WS1-05: Update scenario_config.json with `problems` array + expanded findings
- [ ] WS1-06: Update reference.json source catalog for new schema
- [ ] WS1-07: Regenerate scenario.db and validate data integrity

---

## WS2: Agents — More Capable and Robust

> Status: **Not Started** — depends on WS1 completion

- [ ] WS2-01: Expand context window with sliding summary (last 8 full + older compressed)
- [ ] WS2-02: Add investigation phase awareness to agent system prompts
- [ ] WS2-03: Improve clarification intelligence with metadata-first resolution
- [ ] WS2-04: Add proactive guidance hints without answer leakage
- [ ] WS2-05: Improve multi-step investigation loop (don't exit early)
- [ ] WS2-06: Add follow-up question threading (detect anaphoric references)
- [ ] WS2-07: Add response grounding validation (flag hallucinated numbers)

---

## WS3: Submission and Evaluation Framework

> Status: **Not Started** — depends on WS1 + WS2

- [ ] WS3-01: Define multi-problem scoring rubric (easy=1pt, medium=3pt, hard=5pt)
- [ ] WS3-02: Update scorer to evaluate multiple problems separately
- [ ] WS3-03: Add difficulty-aware process signal scoring
- [ ] WS3-04: Redesign post-submission flow (auto-trigger scoring, redirect to review)
- [ ] WS3-05: Add problem-tier breakdown to review page
- [ ] WS3-06: Add pass/fail verdict with thresholds
- [ ] WS3-07: Add investigation replay timeline on review page
