import { buildLandingAuthUrl, inferCompanyIntent } from "@/lib/auth-routing";

function normalizeApiBase(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, "");
  if (trimmed.endsWith("/api/v1")) {
    return trimmed.slice(0, -"/api/v1".length);
  }
  return trimmed;
}

const API_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000");
const PREFIX = "/api/v1";

let _authToken: string | null = null;

export function setAuthToken(token: string | null) {
  _authToken = token;
}

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (_authToken) {
    headers["Authorization"] = `Bearer ${_authToken}`;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers,
      ...init,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown network error";
    throw new Error(`Cannot reach backend at ${API_BASE}${path}: ${message}`);
  }
  if (res.status === 401 && typeof window !== "undefined") {
    const nextPath = `${window.location.pathname}${window.location.search}`;
    if (window.location.pathname !== "/") {
      window.location.href = buildLandingAuthUrl({
        auth: inferCompanyIntent(nextPath) ? "company" : "candidate",
        next: nextPath,
      });
    }
    throw new Error("Session expired");
  }
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ────────────────────────────────────────────────────────────

export interface Scenario {
  id: string;
  title: string;
  difficulty: string;
  description?: string;
  scenario_type?: string;
  industry?: string | null;
  product?: string | null;
  icon?: string | null;
}

export interface Challenge {
  id: string;
  challenge_title: string;
  challenge_prompt: string;
}

interface ArtifactBase {
  title: string;
  summary?: string;
  citation_ids: string[];
}

export interface MetricArtifact extends ArtifactBase {
  kind: "metric";
  value?: string | number;
  label?: string;
  change?: number;
  unit?: string;
  subtitle?: string;
  labels?: string[];
  series?: { name: string; values: number[] }[];
  columns?: string[];
  rows?: Record<string, string | number | null>[];
}

export interface ChartArtifact extends ArtifactBase {
  kind: "chart";
  chart_type?: "bar" | "line" | "funnel" | "pie" | "scatter" | "heatmap" | "histogram" | "box" | "dual_axis_line";
  labels: string[];
  series: { name: string; values: number[] }[];
  multi_measure?: boolean;
  dual_axis?: boolean;
  primary_unit?: string;
  secondary_unit?: string;
  unit?: string;
  columns?: string[];
  rows?: Record<string, string | number | null>[];
}

export interface TableArtifact extends ArtifactBase {
  kind: "table";
  columns: string[];
  rows: Record<string, string | number | null>[];
  labels?: string[];
  series?: { name: string; values: number[] }[];
  display_clarification?: string;
}

export interface VegaChartArtifact extends ArtifactBase {
  kind: "vega_chart";
  vega_spec: Record<string, unknown>;
  columns?: string[];
  rows?: Record<string, string | number | null>[];
}

export type Artifact = MetricArtifact | ChartArtifact | TableArtifact | VegaChartArtifact;

export interface Citation {
  citation_id: string;
  source: string;
  description?: string;
}

export interface PendingFollowUp {
  prompt: string;
  choices: string[];
  default_choice: string;
  resolved_query_template: string;
  allow_free_text?: boolean;
  clarification_count?: number;
}

export interface QueryHistoryItem {
  query_log_id: number;
  agent: string;
  query: string;
  response: string;
  artifacts: Artifact[];
  citations: Citation[];
  warnings: string[];
  planner?: {
    pending_follow_up?: PendingFollowUp | null;
    next_steps?: string[];
    [key: string]: unknown;
  };
  timestamp: string;
}

export interface SavedEvidence {
  id: number;
  query_log_id: number;
  citation_id: string;
  agent: string;
  artifact: Artifact;
  citation: Citation;
  annotation: string | null;
  query_text: string;
  saved_at: string;
}

interface ReferenceField {
  name: string;
  type: string;
  description: string;
}

interface ReferenceSource {
  name: string;
  description: string;
  fields: ReferenceField[];
}

interface ReferenceSourceDomain {
  domain: string;
  agent: string;
  sources: ReferenceSource[];
}

interface GlossaryItem {
  term: string;
  definition: string;
}

export interface ReferencePanel {
  mission_brief?: {
    problem?: string;
    objective?: string;
    notes?: string[];
  };
  source_catalog: ReferenceSourceDomain[];
  glossary: GlossaryItem[];
}

export interface ScenarioDetail {
  scenario_id: string;
  title: string;
  problem_statement: string;
  reference_panel: ReferencePanel;
  agent_profiles: Record<string, unknown>;
}

export interface SessionStatus {
  session_id: string;
  scenario_id: string;
  time_remaining_minutes: number;
  queries_made: number;
  saved_evidence_count: number;
}

interface QueryResponse {
  agent: string;
  response: string;
  artifacts: Artifact[];
  citations: Citation[];
  warnings: string[];
  next_steps: string[];
  pending_follow_up: PendingFollowUp | null;
  intent_class: string;
  query_log_id: number;
}

export interface ProposedAction {
  action: string;
  priority: "P0" | "P1" | "P2";
}

export interface DimensionScore {
  score: number;
  level: string;
  weight: number;
  reasoning: string;
}

export interface ScoringResult {
  overall_score: number;
  dimensions: Record<string, DimensionScore>;
  process_signals: {
    total_queries: number;
    evidence_saved_count: number;
    agents_used: Record<string, number>;
    typed_vs_suggestion: { typed: number; suggestion: number };
    session_duration_minutes: number;
  };
  highlights: string[];
  missed_signals: string[];
  red_herrings_engaged: string[];
  scored_at?: string;
}

export interface QueryLogDetail {
  query_log_id: number;
  agent: string;
  query: string;
  response: string;
  artifacts: Artifact[];
  citations: Citation[];
  warnings: string[];
  planner: {
    question_understanding?: string;
    complexity?: string;
    target_tables?: string[];
    stop_condition?: string;
    [key: string]: unknown;
  };
  attempts: {
    attempt?: number;
    status?: string;
    title?: string;
    kind?: string;
    answer_mode?: string;
    sql?: string;
    python_code?: string;
    error?: string;
    summary?: string;
    sources?: string[];
    rejection_reason?: string;
    suggested_fix?: string;
    critic_ok?: boolean;
    critic_reason?: string;
    duration_ms?: number;
    rows_returned?: number;
    [key: string]: unknown;
  }[];
  trace?: {
    intent?: string;
    question_understanding?: string;
    sub_questions?: string[];
    effective_query?: string | null;
    conversation_turns?: number;
    plan_complexity?: string;
    total_attempts?: number;
    evidence_collected?: number;
    total_duration_ms?: number;
    [key: string]: unknown;
  };
  llm_calls?: {
    stage: string;
    step?: number;
    system_prompt?: string;
    user_payload?: Record<string, unknown>;
    raw_response?: string;
    parsed_result?: unknown;
    duration_ms?: number;
  }[];
  timestamp: string;
}

// ── API functions ────────────────────────────────────────────────────

export async function listScenarios(): Promise<{ scenarios: Scenario[] }> {
  return fetchJSON(`${PREFIX}/scenarios`);
}

export async function startSession(
  candidateId: string,
  scenarioId: string,
  challengeId?: string
): Promise<{ session_id: string }> {
  return fetchJSON(`${PREFIX}/sessions/start`, {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      scenario_id: scenarioId,
      challenge_id: challengeId,
    }),
  });
}

export async function getChallenges(
  scenarioId: string
): Promise<{ scenario_id: string; challenges: Challenge[] }> {
  return fetchJSON(`${PREFIX}/scenarios/${scenarioId}/challenges`);
}

export async function getScenarioDetails(sessionId: string): Promise<ScenarioDetail> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/scenario`);
}

export async function queryAgent(
  sessionId: string,
  agent: string,
  query: string,
  inputMode: "typed" | "suggestion" = "typed"
): Promise<QueryResponse> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/query`, {
    method: "POST",
    body: JSON.stringify({ agent, query, input_mode: inputMode }),
  });
}

export async function queryAgentStream(
  sessionId: string,
  agent: string,
  query: string,
  onStatus: (stage: string, detail: string) => void,
  inputMode: "typed" | "suggestion" = "typed"
): Promise<QueryResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (_authToken) {
    headers["Authorization"] = `Bearer ${_authToken}`;
  }
  const response = await fetch(`${API_BASE}${PREFIX}/sessions/${sessionId}/query/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ agent, query, input_mode: inputMode }),
  });
  if (!response.ok || !response.body) {
    // Fallback to non-streaming endpoint
    return queryAgent(sessionId, agent, query, inputMode);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const event = JSON.parse(line.slice(6));
        if (event.stage === "complete") {
          return event.result as QueryResponse;
        }
        onStatus(event.stage || "", event.detail || "");
      } catch {
        // ignore malformed SSE lines
      }
    }
  }
  // If we exit without a complete event, fall back
  return queryAgent(sessionId, agent, query, inputMode);
}

export async function getSessionStatus(sessionId: string): Promise<SessionStatus> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/status`);
}

export async function getQueryHistory(
  sessionId: string
): Promise<{ queries: QueryHistoryItem[] }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/history`);
}

export async function getSavedEvidence(
  sessionId: string
): Promise<{ evidence: SavedEvidence[] }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/evidence`);
}

export async function saveEvidence(
  sessionId: string,
  queryLogId: number,
  citationId: string,
  agent: string,
  annotation?: string
): Promise<{ status: string; saved_evidence_id: number; evidence_count: number }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/evidence`, {
    method: "POST",
    body: JSON.stringify({
      query_log_id: queryLogId,
      citation_id: citationId,
      agent,
      annotation: annotation || null,
    }),
  });
}

export async function removeEvidence(
  sessionId: string,
  savedEvidenceId: number
): Promise<{ status: string; evidence_count: number }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/evidence/${savedEvidenceId}`, {
    method: "DELETE",
  });
}

export async function updateEvidenceAnnotation(
  sessionId: string,
  savedEvidenceId: number,
  annotation: string | null
): Promise<{ status: string }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/evidence/${savedEvidenceId}`, {
    method: "PATCH",
    body: JSON.stringify({ annotation }),
  });
}

export async function logSessionEvent(
  sessionId: string,
  eventType: string,
  eventPayload: Record<string, unknown> = {}
): Promise<{ status: string; event_id: number }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/events`, {
    method: "POST",
    body: JSON.stringify({ event_type: eventType, event_payload: eventPayload }),
  });
}

export async function submitSolution(
  sessionId: string,
  rootCause: string,
  supportingEvidenceIds: number[],
  proposedActions: ProposedAction[],
  stakeholderSummary: string
): Promise<{ status: string; session_complete: boolean; submission_id: number }> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      root_cause: rootCause,
      supporting_evidence_ids: supportingEvidenceIds,
      proposed_actions: proposedActions,
      stakeholder_summary: stakeholderSummary,
    }),
  });
}

export async function scoreSession(
  sessionId: string
): Promise<Record<string, unknown>> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/score`, { method: "POST" });
}

export async function getScore(
  sessionId: string
): Promise<Record<string, unknown>> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/score`);
}

export async function triggerScoring(
  sessionId: string
): Promise<ScoringResult> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/score`, { method: "POST" });
}

export async function getScoringResult(
  sessionId: string
): Promise<ScoringResult> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/score`);
}

export async function getQueryLogDetail(
  sessionId: string,
  queryLogId: number
): Promise<QueryLogDetail> {
  return fetchJSON(`${PREFIX}/sessions/${sessionId}/query/${queryLogId}`);
}

// ── User / Role ─────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  name?: string | null;
  picture?: string | null;
  role: string;
  company_id?: number | null;
}

export async function getMe(): Promise<UserProfile> {
  return fetchJSON(`${PREFIX}/me`);
}

export async function setMyRole(role: "company" | "candidate"): Promise<{ role: string }> {
  return fetchJSON(`${PREFIX}/me/role`, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}

export interface UserSessionSummary {
  session_id: string;
  scenario_id: string;
  challenge_id?: string | null;
  assessment_id?: string | null;
  invite_token?: string | null;
  started_at: string;
  status: string;
  assessment_title?: string | null;
  company_name?: string | null;
}

export async function getMySessions(): Promise<{ sessions: UserSessionSummary[] }> {
  return fetchJSON(`${PREFIX}/me/sessions`);
}

// ── Company ─────────────────────────────────────────────────────────

export async function createCompany(name: string): Promise<{ id: number; name: string }> {
  return fetchJSON(`${PREFIX}/companies`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function getMyCompany(): Promise<{ id: number; name: string; owner_user_id: string }> {
  return fetchJSON(`${PREFIX}/companies/me`);
}

// ── Assessments ─────────────────────────────────────────────────────

export interface Assessment {
  id: string;
  company_id: number;
  scenario_id: string;
  challenge_id?: string | null;
  title?: string | null;
  created_at: string;
  candidate_total: number;
  candidate_completed: number;
  candidate_active: number;
}

export interface AssessmentCandidate {
  session_id: string;
  candidate_id: string;
  started_at: string;
  ended_at?: string | null;
  status: string;
  email?: string | null;
  name?: string | null;
  picture?: string | null;
  overall_score?: number | null;
  scored_at?: string | null;
}

export interface InviteInfo {
  token: string;
  candidate_email?: string | null;
  created_at: string;
  used_at?: string | null;
  claimed_by_email?: string | null;
  claimed_by_name?: string | null;
}

export async function createAssessment(
  scenarioId: string,
  challengeId?: string | null,
  title?: string | null,
): Promise<{ id: string }> {
  return fetchJSON(`${PREFIX}/assessments`, {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId, challenge_id: challengeId, title }),
  });
}

export async function listAssessments(): Promise<{ assessments: Assessment[] }> {
  return fetchJSON(`${PREFIX}/assessments`);
}

export async function getAssessmentDetail(
  assessmentId: string
): Promise<{ assessment: Assessment; candidates: AssessmentCandidate[]; invites: InviteInfo[] }> {
  return fetchJSON(`${PREFIX}/assessments/${assessmentId}`);
}

export async function generateInvite(
  assessmentId: string,
  candidateEmail?: string
): Promise<{ token: string; invite_url: string }> {
  return fetchJSON(`${PREFIX}/assessments/${assessmentId}/invite`, {
    method: "POST",
    body: JSON.stringify({ candidate_email: candidateEmail || null }),
  });
}

// ── Invite ──────────────────────────────────────────────────────────

export interface InviteValidation {
  token: string;
  scenario_id: string;
  assessment_title?: string | null;
  company_name?: string | null;
}

export async function validateInvite(token: string): Promise<InviteValidation> {
  return fetchJSON(`${PREFIX}/invite/${token}`);
}

export async function claimInvite(token: string): Promise<{ session_id: string; claimed: boolean; company_name?: string; assessment_title?: string }> {
  return fetchJSON(`${PREFIX}/invite/${token}/claim`, { method: "POST" });
}
