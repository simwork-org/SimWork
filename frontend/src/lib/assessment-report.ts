import type {
  DimensionScore,
  QueryHistoryItem,
  SavedEvidence,
  ScenarioDetail,
  ScoringResult,
  SessionSubmission,
} from "@/lib/api";

export type RecommendationTier = "Strong Hire" | "Hire" | "Mixed" | "No Hire";
export type ConfidenceTier = "High" | "Medium" | "Low";

export interface CapabilitySignal {
  key: string;
  label: string;
  score: number;
  normalizedScore: number;
  weight: number;
  level: string;
  reasoning: string;
}

export interface QuantMetric {
  label: string;
  value: string | number;
  helper: string;
}

export interface AssessmentReportModel {
  overallScore: number;
  recommendation: RecommendationTier;
  confidence: ConfidenceTier;
  scenarioTitle: string;
  scenarioSummary: string;
  capabilitySignals: CapabilitySignal[];
  strengths: string[];
  risks: string[];
  executiveSummary: string;
  quantMetrics: QuantMetric[];
  timeline: { label: string; value: string }[];
  evidenceInsights: {
    linkedEvidenceCount: number;
    annotatedEvidenceCount: number;
    findingsCoverage: number;
    redHerringsEngaged: number;
    evidenceLinkageScore: number;
  };
  decisionInsights: {
    actionCount: number;
    prioritizedActionCount: number;
    communicationScore: number;
    actionabilityScore: number;
    investigationBreadthScore: number;
  };
}

function humanizeKey(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizeFivePointScore(score: number): number {
  return Math.round((score / 5) * 100);
}

function clamp(value: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, Math.round(value)));
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function computeActionabilityScore(submission: SessionSubmission): number {
  const actions = submission.proposed_actions ?? [];
  if (actions.length === 0) return 15;

  const withPriority = actions.filter((action) => action.priority).length;
  const averageActionLength = average(actions.map((action) => action.action.trim().split(/\s+/).length));
  const evidenceSupportRatio = Math.min(
    1,
    submission.supporting_evidence_ids.length / Math.max(actions.length, 1)
  );

  return clamp(
    withPriority / actions.length * 35 +
      Math.min(averageActionLength / 12, 1) * 25 +
      evidenceSupportRatio * 40
  );
}

function computeInvestigationBreadthScore(
  scoring: ScoringResult,
  queryHistory: QueryHistoryItem[],
  evidence: SavedEvidence[]
): number {
  const agentCount = Object.keys(scoring.process_signals.agents_used || {}).length;
  const queryCount = queryHistory.length || scoring.process_signals.total_queries || 0;
  const evidenceRatio = evidence.length / Math.max(queryCount, 1);
  const redHerringPenalty = Math.min(scoring.red_herrings_engaged.length * 7, 20);

  return clamp(
    (agentCount / 3) * 45 +
      Math.min(queryCount / 10, 1) * 30 +
      Math.min(evidenceRatio / 0.35, 1) * 25 -
      redHerringPenalty
  );
}

function computeEvidenceLinkageScore(
  submission: SessionSubmission,
  evidence: SavedEvidence[],
  findingsCoverage: number
): number {
  const linkedEvidenceCount = submission.supporting_evidence_ids.length;
  const annotatedEvidenceCount = evidence.filter((item) => !!item.annotation?.trim()).length;
  return clamp(
    Math.min(linkedEvidenceCount / 4, 1) * 40 +
      Math.min(annotatedEvidenceCount / Math.max(evidence.length, 1), 1) * 25 +
      findingsCoverage * 35
  );
}

function computeConfidence(
  scoring: ScoringResult,
  submission: SessionSubmission,
  queryHistory: QueryHistoryItem[],
  evidence: SavedEvidence[]
): ConfidenceTier {
  const findingsTotal = scoring.highlights.length + scoring.missed_signals.length;
  const findingsCoverage = findingsTotal > 0 ? scoring.highlights.length / findingsTotal : 0.5;
  const evidenceQuality = evidence.filter((item) => !!item.annotation?.trim()).length / Math.max(evidence.length, 1);
  const agentCount = Object.keys(scoring.process_signals.agents_used || {}).length;
  const actionCount = submission.proposed_actions.length;

  const confidenceScore =
    findingsCoverage * 35 +
    evidenceQuality * 20 +
    Math.min(queryHistory.length / 10, 1) * 15 +
    Math.min(agentCount / 3, 1) * 15 +
    Math.min(actionCount / 3, 1) * 15;

  if (confidenceScore >= 72) return "High";
  if (confidenceScore >= 48) return "Medium";
  return "Low";
}

function computeRecommendation(
  overallScore: number,
  criticalRisk: boolean,
  confidence: ConfidenceTier
): RecommendationTier {
  if (criticalRisk || overallScore < 55) return "No Hire";
  if (overallScore < 70) return "Mixed";
  if (overallScore >= 85 && confidence !== "Low") return "Strong Hire";
  return "Hire";
}

function buildStrengths(signals: CapabilitySignal[], scoring: ScoringResult): string[] {
  const strengths = signals
    .filter((signal) => signal.normalizedScore >= 75)
    .sort((a, b) => b.normalizedScore - a.normalizedScore)
    .slice(0, 3)
    .map((signal) => `${signal.label}: ${signal.reasoning}`);

  if (scoring.highlights.length > 0) {
    strengths.push(`Captured ${scoring.highlights.length} critical findings from the scenario evidence.`);
  }

  return strengths.slice(0, 3);
}

function buildRisks(
  signals: CapabilitySignal[],
  scoring: ScoringResult,
  investigationBreadthScore: number
): string[] {
  const risks = signals
    .filter((signal) => signal.normalizedScore < 70)
    .sort((a, b) => a.normalizedScore - b.normalizedScore)
    .slice(0, 3)
    .map((signal) => `${signal.label}: ${signal.reasoning}`);

  if (investigationBreadthScore < 55) {
    risks.push("Investigation breadth was narrow relative to the scenario complexity.");
  }
  if (scoring.missed_signals.length > 0) {
    risks.push(`Missed ${scoring.missed_signals.length} expected findings that mattered to the final recommendation.`);
  }
  return risks.slice(0, 3);
}

export function buildAssessmentReportModel(params: {
  scenario: ScenarioDetail;
  scoring: ScoringResult;
  submission: SessionSubmission;
  evidence: SavedEvidence[];
  queryHistory: QueryHistoryItem[];
}): AssessmentReportModel {
  const { scenario, scoring, submission, evidence, queryHistory } = params;
  const overallScore = normalizeFivePointScore(scoring.overall_score);
  const capabilitySignals = Object.entries(scoring.dimensions).map(([key, value]: [string, DimensionScore]) => ({
    key,
    label: humanizeKey(key),
    score: value.score,
    normalizedScore: normalizeFivePointScore(value.score),
    weight: value.weight,
    level: value.level,
    reasoning: value.reasoning,
  }));

  const findingsTotal = scoring.highlights.length + scoring.missed_signals.length;
  const findingsCoverage = findingsTotal > 0 ? scoring.highlights.length / findingsTotal : 0.5;
  const investigationBreadthScore = computeInvestigationBreadthScore(scoring, queryHistory, evidence);
  const actionabilityScore = computeActionabilityScore(submission);
  const communicationSignal = capabilitySignals.find((signal) =>
    /communication|stakeholder|summary/i.test(signal.key)
  );
  const communicationScore = communicationSignal?.normalizedScore ?? clamp(
    Math.min(submission.stakeholder_summary.trim().split(/\s+/).length / 45, 1) * 100
  );
  const evidenceLinkageScore = computeEvidenceLinkageScore(submission, evidence, findingsCoverage);
  const confidence = computeConfidence(scoring, submission, queryHistory, evidence);
  const criticalRisk =
    capabilitySignals.some((signal) => /root|diagnos|problem/i.test(signal.key) && signal.normalizedScore < 55) ||
    capabilitySignals.some((signal) => /solution|decision|feature|pricing/i.test(signal.key) && signal.normalizedScore < 50);
  const recommendation = computeRecommendation(overallScore, criticalRisk, confidence);
  const strengths = buildStrengths(capabilitySignals, scoring);
  const risks = buildRisks(capabilitySignals, scoring, investigationBreadthScore);

  const quantMetrics: QuantMetric[] = [
    {
      label: "Overall Score",
      value: `${overallScore}/100`,
      helper: "Weighted scenario evaluation normalized to a hiring-friendly scale.",
    },
    {
      label: "Agents Used",
      value: Object.keys(scoring.process_signals.agents_used || {}).length,
      helper: "Distinct teammate perspectives used during the investigation.",
    },
    {
      label: "Evidence Saved",
      value: evidence.length,
      helper: "Items explicitly preserved by the candidate for the final case.",
    },
    {
      label: "Findings Coverage",
      value: `${Math.round(findingsCoverage * 100)}%`,
      helper: "Expected high-signal findings captured versus missed.",
    },
    {
      label: "Evidence Linkage",
      value: `${evidenceLinkageScore}/100`,
      helper: "How well the final recommendation is supported by selected and annotated evidence.",
    },
    {
      label: "Actionability",
      value: `${actionabilityScore}/100`,
      helper: "Quality of proposed actions based on priority, specificity, and evidence support.",
    },
    {
      label: "Investigation Breadth",
      value: `${investigationBreadthScore}/100`,
      helper: "Coverage across agents, queries, and evidence relative to scenario complexity.",
    },
    {
      label: "Duration",
      value: `${scoring.process_signals.session_duration_minutes} min`,
      helper: "Elapsed time from session start to final submission.",
    },
  ];

  const timeline = [
    { label: "Started", value: queryHistory[0]?.timestamp ? new Date(queryHistory[0].timestamp).toLocaleString() : "—" },
    { label: "Submitted", value: new Date(submission.timestamp).toLocaleString() },
    { label: "Query Volume", value: `${queryHistory.length} queries` },
    { label: "Evidence Linked", value: `${submission.supporting_evidence_ids.length} supporting items` },
  ];

  return {
    overallScore,
    recommendation,
    confidence,
    scenarioTitle: scenario.title,
    scenarioSummary: scenario.problem_statement,
    capabilitySignals,
    strengths,
    risks,
    executiveSummary:
      `${recommendation} with ${confidence.toLowerCase()} confidence. ` +
      `The candidate scored ${overallScore}/100 on this ${scenario.title} simulation, ` +
      `showing strongest signal in ${capabilitySignals.sort((a, b) => b.normalizedScore - a.normalizedScore)[0]?.label?.toLowerCase() || "core PM judgment"} ` +
      `while the main caution area is ${risks[0]?.toLowerCase() || "evidence depth"}.`,
    quantMetrics,
    timeline,
    evidenceInsights: {
      linkedEvidenceCount: submission.supporting_evidence_ids.length,
      annotatedEvidenceCount: evidence.filter((item) => !!item.annotation?.trim()).length,
      findingsCoverage: Math.round(findingsCoverage * 100),
      redHerringsEngaged: scoring.red_herrings_engaged.length,
      evidenceLinkageScore,
    },
    decisionInsights: {
      actionCount: submission.proposed_actions.length,
      prioritizedActionCount: submission.proposed_actions.filter((action) => !!action.priority).length,
      communicationScore,
      actionabilityScore,
      investigationBreadthScore,
    },
  };
}
