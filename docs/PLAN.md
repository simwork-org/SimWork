# Candidate-Curated Evidence Flow, Connected Submission, and Full Action Logging

## Summary

- Keep agents as chat-first teammates. Every answer, whether text, chart, metric, or table, should appear inline in the chat thread only.
- Change the Evidence Board from an auto-filled system feed into a candidate-owned case file. Candidates explicitly save chat artifacts they think matter, optionally annotate them, and use those saved items in the final submission.
- Remove the separate hypothesis feature. The saved evidence set plus the final submission becomes the candidate’s reasoning trace.
- Add a complete session action log so scoring can evaluate not just the final answer, but also the kind of questions asked, the order of investigation, what the candidate chose to save, and how they navigated the workflow.

## Key Changes

### 1. Make artifacts chat-native, not board-native

- Change the workspace data model so agent messages can include zero or more inline artifacts.
- Reuse the existing artifact renderers in chat:
  - `metric`
  - `chart`
  - `table`
- Keep the chart wire type limited to artifact kinds the backend can actually emit in this pass; do not expand to new chart schemas unless backend generation is ready.
- Remove automatic Evidence Board population from:
  - live query responses
  - history reconstruction on reload
- Agent responses remain text plus inline artifacts; the board starts empty every session unless the candidate saves items.

### 2. Replace hypothesis with saved evidence

- Remove the footer hypothesis input, saved hypothesis sidebar section, and hypothesis count in session stats.
- Keep old DB hypothesis tables/columns for backward compatibility, but stop writing to them and stop exposing them in session status.
- Add a new `saved_evidence` table in the session DB layer.

Recommended schema:
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `session_id TEXT NOT NULL`
- `query_log_id INTEGER NOT NULL`
- `citation_id TEXT NOT NULL`
- `agent TEXT NOT NULL`
- `annotation TEXT`
- `saved_at TEXT NOT NULL`
- unique constraint on `(session_id, query_log_id, citation_id)`

Design choice:
- Do not store duplicated `artifact_json` or `citation_json` in `saved_evidence`.
- Source of truth stays in `query_logs.artifacts_json` and `query_logs.citations_json`.
- Saved evidence rows reference immutable logged artifacts by `query_log_id + citation_id`.

Backend additions:
- `save_evidence(session_id, query_log_id, citation_id, agent, annotation?)`
- `remove_evidence(session_id, query_log_id, citation_id)`
- `update_evidence_annotation(session_id, query_log_id, citation_id, annotation)`
- `get_saved_evidence(session_id)` returning resolved artifact + citation + annotation + saved timestamp

API additions:
- `GET /sessions/{id}/evidence`
- `POST /sessions/{id}/evidence`
- `PATCH /sessions/{id}/evidence/{saved_id}` or path by `(query_log_id, citation_id)` if used consistently
- `DELETE /sessions/{id}/evidence/{saved_id}`

Frontend behavior:
- Every inline artifact in an agent message gets `Save to board`
- Saved state becomes visible immediately as `Saved`
- Optional one-line annotation at save time; editable later from the board
- Evidence Board shows only saved items, newest first, with remove/edit annotation controls

### 3. Add full session action logging for evaluation

- Add a new append-only `session_events` table as the canonical process log.

Recommended schema:
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `session_id TEXT NOT NULL`
- `event_type TEXT NOT NULL`
- `event_payload_json TEXT NOT NULL`
- `timestamp TEXT NOT NULL`
- `sequence_number INTEGER NOT NULL`

Design rules:
- `sequence_number` must be monotonic per session
- event payloads should be small, structured, and stable
- this is the source of truth for process scoring, not UI-local state

Minimum events to log:
- `session_started`
- `agent_selected`
- `query_submitted`
- `suggestion_clicked`
- `reference_opened`
- `reference_tab_changed`
- `artifact_saved`
- `artifact_removed`
- `artifact_annotation_updated`
- `submission_started`
- `submission_evidence_selected`
- `submission_completed`

Event payload expectations:
- `query_submitted`
  - `agent`
  - `query_text`
  - `input_mode: typed | suggestion`
  - `query_log_id` once available
- `agent_selected`
  - `agent`
- `artifact_saved`
  - `query_log_id`
  - `citation_id`
  - `agent`
- `submission_evidence_selected`
  - `saved_evidence_id`
- `submission_completed`
  - `submission_id`

Implementation detail:
- `query_logs` remains the content log for questions and responses
- `session_events` becomes the behavior log for ordered actions
- scoring uses both together

API additions:
- preferably no generic public event-ingest endpoint
- instead, log events inside existing action endpoints where possible
- add one narrow endpoint for pure UI interactions that do not already hit the backend:
  - `POST /sessions/{id}/events`
  - body: `{ event_type, event_payload }`
- only allow whitelisted event types server-side

### 4. Connect final submission to investigation output

- Redesign the completion page so it loads the candidate’s saved evidence and requires explicit linkage between conclusion and evidence.
- Replace the current submission payload with:
  - `root_cause: string`
  - `supporting_evidence_ids: number[]`
  - `proposed_actions: { action: string; priority: "P0" | "P1" | "P2" }[]`
  - `stakeholder_summary: string`
- Store this in `submissions` with new columns:
  - `supporting_evidence_ids_json`
  - `stakeholder_summary`
- Keep the existing `summary` column only if a compatibility migration is needed; otherwise rename semantically in code now.

Completion page layout:
- Left column: root cause, structured actions, stakeholder summary
- Right column: saved evidence list with checkboxes
- Validation:
  - root cause required
  - at least 1 supporting evidence item required
  - at least 1 non-empty action required
  - stakeholder summary required
- Post-submit success state should summarize:
  - root cause
  - evidence linked count
  - actions count
  - submitted status
- Remove the fake “AI evaluation engine is processing” copy unless scoring is actually triggered.

### 5. Capture scoring inputs now so hybrid evaluation is real later

- Do not rely only on final submission text.
- Future scoring must combine:
  - `query_logs` for question quality and response context
  - `session_events` for action order and behavior
  - `saved_evidence` for candidate judgment
  - `submissions` for final output quality
- Deterministic process signals to compute from logs:
  - agents used
  - query count
  - query ordering by domain
  - first cross-agent query timing
  - typed vs suggestion-driven query mix
  - saved evidence count
  - saved evidence source mix
  - whether key evidence was saved
  - whether red herrings were investigated or saved
  - linked evidence count at submission
  - time from first key finding to final submission
- Do not implement vague signals like `hypothesis_evolution` in this pass unless they are defined from logged behavior.

If scoring is included in this pass:
- make it async:
  - `POST /sessions/{id}/score`
  - `GET /sessions/{id}/score`
- submit returns immediately; scoring runs separately
- scoring result should reference both process and output evidence

## Public Interfaces and Types

Add to query/history types:
- `query_log_id` on query responses and history items so saved evidence can reference persisted artifacts safely
- agent chat messages may include `artifacts: Artifact[]`

Add new frontend types:
- `SavedEvidence`
  - `id`
  - `query_log_id`
  - `citation_id`
  - `agent`
  - `artifact`
  - `citation`
  - `annotation`
  - `saved_at`
- `SessionEvent`
  - `id`
  - `event_type`
  - `event_payload`
  - `timestamp`
  - `sequence_number`

Replace submission API type with structured payload:
- `rootCause`
- `supportingEvidenceIds`
- `proposedActions: { action, priority }[]`
- `stakeholderSummary`

Remove hypothesis API usage from the frontend and stop depending on `current_hypothesis` in session status.

## Test Plan

- Workspace:
  - agent answers render artifacts inline in chat
  - Evidence Board stays empty until candidate saves something
  - saving an artifact adds it to the board and persists across reload
  - removing or editing annotation updates persisted saved evidence
  - no artifact auto-populates the board from history
- Action logging:
  - agent switch logs `agent_selected`
  - typed question logs `query_submitted` with `input_mode=typed`
  - suggestion click logs `suggestion_clicked` and `query_submitted`
  - reference drawer interactions log the correct event types
  - save/remove/edit evidence actions log matching events
  - submission start, evidence selection, and completion are logged in order
  - sequence numbers are monotonic within a session
- Data model / API:
  - `query_log_id` is returned and stable
  - saving the same artifact twice is prevented by uniqueness
  - saved evidence resolves correctly from `query_logs`
- Submission:
  - candidate can only submit with at least one linked evidence item
  - structured actions persist with priority
  - completion page reloads saved evidence and preserves selections
- Regression:
  - existing query flow still works
  - existing artifact rendering still works inline
  - old sessions without saved evidence still load cleanly
- If scoring endpoints are included:
  - scoring can reconstruct process from `session_events`
  - submit does not block on scoring
  - score status can be polled independently

## Assumptions and Defaults

- Default: no separate hypothesis feature; curated evidence is the hypothesis trace.
- Default: Evidence Board is candidate-curated only, never auto-filled.
- Default: inline artifact rendering in chat is required before evidence curation is useful.
- Default: scoring/reviewer UI is a follow-up phase unless you explicitly want a larger, riskier all-in-one implementation.
- Default storage model: saved evidence references logged artifacts instead of duplicating artifact payloads.
- Default evaluation model: candidate process is scored using both `query_logs` and append-only `session_events`, never from final submission alone.
