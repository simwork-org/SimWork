"use client";

import { useMemo, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthToken } from "@/lib/useAuthToken";
import {
  getMe,
  getMySessions,
  getQueryHistory,
  getSavedEvidence,
  getScenarioDetails,
  getScoringResult,
  getSubmission,
  triggerScoring,
  type Artifact,
  type QueryHistoryItem,
  type SavedEvidence,
  type ScenarioDetail,
  type ScoringResult,
  type SessionSubmission,
} from "@/lib/api";
import { buildAssessmentReportModel } from "@/lib/assessment-report";
import { findAssignedSession } from "@/lib/auth-routing";

const RECOMMENDATION_STYLES: Record<string, string> = {
  "Strong Hire": "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Hire: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  Mixed: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  "No Hire": "bg-red-500/15 text-red-300 border-red-500/30",
};

function ReviewVegaChart({ spec }: { spec: Record<string, unknown> }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<unknown>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;

    import("vega-embed").then(({ default: vegaEmbed }) => {
      if (cancelled || !containerRef.current) return;
      vegaEmbed(containerRef.current, spec as never, {
        actions: false,
        renderer: "svg",
        config: {
          background: "transparent",
          view: { stroke: "transparent" },
          axis: { labelColor: "#94a3b8", titleColor: "#94a3b8", gridColor: "#1e293b", domainColor: "#334155" },
          legend: { labelColor: "#94a3b8", titleColor: "#94a3b8" },
          title: { color: "#e2e8f0" },
        },
      }).then((result) => {
        viewRef.current = result.view;
      });
    });

    return () => {
      cancelled = true;
      if (viewRef.current && typeof (viewRef.current as { finalize?: () => void }).finalize === "function") {
        (viewRef.current as { finalize: () => void }).finalize();
      }
    };
  }, [spec]);

  return <div ref={containerRef} className="w-full" />;
}

function ReviewArtifactView({ artifact }: { artifact: Artifact }) {
  if (artifact.kind === "metric") {
    return (
      <div className="mt-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 p-3 text-center">
        <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{artifact.value}</p>
        {artifact.subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{artifact.subtitle}</p>}
      </div>
    );
  }

  if (artifact.kind === "table") {
    const previewRows = artifact.rows.slice(0, 5);
    return (
      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/50">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800/60">
              {artifact.columns.map((col) => (
                <th key={col} className="px-3 py-1.5 text-left font-semibold text-slate-500 whitespace-nowrap">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {previewRows.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white dark:bg-slate-900/20" : "bg-slate-50/50 dark:bg-slate-800/20"}>
                {artifact.columns.map((col) => (
                  <td key={col} className="px-3 py-1.5 text-slate-700 dark:text-slate-300 whitespace-nowrap">{row[col] ?? "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {artifact.rows.length > 5 && (
          <p className="text-[10px] text-slate-400 px-3 py-1 bg-slate-50 dark:bg-slate-800/40">
            +{artifact.rows.length - 5} more rows
          </p>
        )}
      </div>
    );
  }

  if (artifact.kind === "vega_chart") {
    return (
      <div className="mt-3">
        <ReviewVegaChart spec={artifact.vega_spec} />
      </div>
    );
  }

  if (artifact.kind === "chart") {
    const series = artifact.series[0];
    if (!series || series.values.length === 0) return null;
    const max = Math.max(...series.values.map(Math.abs), 1);
    const isLine = artifact.chart_type === "line" || artifact.chart_type === "dual_axis_line";
    if (isLine) {
      const pts = series.values.map((v, i) => ({
        x: (i / Math.max(series.values.length - 1, 1)) * 280,
        y: 60 - (v / max) * 55,
      }));
      return (
        <div className="mt-3">
          <svg viewBox="0 0 280 65" className="w-full h-16">
            <polyline points={pts.map((p) => `${p.x},${p.y}`).join(" ")} fill="none" stroke="#10b981" strokeWidth="2" />
            {pts.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="#10b981" />)}
          </svg>
        </div>
      );
    }

    return (
      <div className="mt-3 flex items-end gap-1 h-16">
        {series.values.slice(0, 12).map((v, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
            <div
              className="w-full rounded-sm bg-emerald-500/70"
              style={{ height: `${Math.max((Math.abs(v) / max) * 52, 2)}px` }}
            />
            {artifact.labels[i] && (
              <span className="text-[8px] text-slate-400 truncate w-full text-center">{artifact.labels[i]}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  return null;
}

function MetricTile({ label, value, helper }: { label: string; value: string | number; helper: string }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-slate-500">{helper}</p>
    </div>
  );
}

function CapabilityCard({
  label,
  score,
  reasoning,
  weight,
}: {
  label: string;
  score: number;
  reasoning: string;
  weight: number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{label}</h3>
          <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{reasoning}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-2xl font-black text-slate-900 dark:text-white">{score}</p>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Weight {(weight * 100).toFixed(0)}%</p>
        </div>
      </div>
      <div className="mt-4 h-2 rounded-full bg-slate-100 dark:bg-slate-800">
        <div className="h-2 rounded-full bg-[#10B981]" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const params = useParams();
  const session = useAuthToken();
  const sessionId = params.sessionId as string;

  const [scoring, setScoring] = useState<ScoringResult | null>(null);
  const [evidence, setEvidence] = useState<SavedEvidence[]>([]);
  const [submission, setSubmission] = useState<SessionSubmission | null>(null);
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>([]);
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [scoringLoading, setScoringLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;

    let cancelled = false;

    async function validateRole() {
      try {
        const me = await getMe();
        if (cancelled) return;

        if (me.role === "company") return;

        const { sessions } = await getMySessions();
        if (cancelled) return;

        const assignedSession = findAssignedSession(sessions);
        router.replace(assignedSession ? `/briefing/${assignedSession.session_id}` : "/candidate");
      } catch {
        if (!cancelled) router.replace("/login?role=company");
      }
    }

    validateRole();
    return () => {
      cancelled = true;
    };
  }, [session, router]);

  useEffect(() => {
    async function load() {
      try {
        const [scoreRes, evidenceRes, submissionRes, historyRes, scenarioRes] = await Promise.allSettled([
          getScoringResult(sessionId),
          getSavedEvidence(sessionId),
          getSubmission(sessionId),
          getQueryHistory(sessionId),
          getScenarioDetails(sessionId),
        ]);

        if (scoreRes.status === "fulfilled") setScoring(scoreRes.value);
        if (evidenceRes.status === "fulfilled") setEvidence(evidenceRes.value.evidence);
        if (submissionRes.status === "fulfilled") setSubmission(submissionRes.value);
        if (historyRes.status === "fulfilled") setQueryHistory(historyRes.value.queries);
        if (scenarioRes.status === "fulfilled") setScenario(scenarioRes.value);
      } catch {
        setError("Failed to load candidate report data.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [sessionId]);

  const report = useMemo(() => {
    if (!scoring || !submission || !scenario) return null;
    return buildAssessmentReportModel({
      scenario,
      scoring,
      submission,
      evidence,
      queryHistory,
    });
  }, [scoring, submission, scenario, evidence, queryHistory]);

  const handleGenerateScore = async () => {
    setScoringLoading(true);
    setError(null);
    try {
      const result = await triggerScoring(sessionId);
      setScoring(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scoring failed");
    } finally {
      setScoringLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f6f6f8] dark:bg-[#101122]">
        <div className="flex items-center gap-3 text-slate-500">
          <span className="material-symbols-outlined animate-spin">progress_activity</span>
          Loading report...
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen w-full flex-col bg-[#f6f6f8] dark:bg-[#101122]">
      <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4 lg:px-10 bg-white dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-[#10B981] text-white">
            <span className="material-symbols-outlined text-xl">cognition</span>
          </div>
          <h2 className="text-slate-900 dark:text-slate-100 text-lg font-bold tracking-tight">SimWork</h2>
          <span className="text-slate-400 mx-2">/</span>
          <span className="text-slate-500 text-sm font-medium">Assessment Report</span>
        </div>
        {report && (
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 font-semibold py-2 px-4 rounded-lg text-sm transition-all"
          >
            <span className="material-symbols-outlined text-sm">download</span>
            Download PDF
          </button>
        )}
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-8 lg:px-10">
        <div className="max-w-6xl mx-auto space-y-8">
          {!scoring && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-8 text-center">
              <span className="material-symbols-outlined text-4xl text-slate-300 dark:text-slate-600 mb-4 block">grading</span>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Assessment report not generated yet</h2>
              <p className="text-sm text-slate-500 mb-6">
                Generate the hiring-manager report to summarize the candidate&apos;s PM judgment, investigation quality, and recommendation strength.
              </p>
              {error && <p className="text-sm text-red-500 mb-4">{error}</p>}
              <button
                onClick={handleGenerateScore}
                disabled={scoringLoading}
                className="inline-flex items-center gap-2 bg-[#10B981] hover:bg-[#10B981]/90 text-white font-bold py-3 px-6 rounded-xl transition-all disabled:opacity-50"
              >
                {scoringLoading ? (
                  <>
                    <span className="material-symbols-outlined animate-spin text-sm">progress_activity</span>
                    Generating...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">auto_awesome</span>
                    Generate Report
                  </>
                )}
              </button>
            </div>
          )}

          {scoring && report && submission && scenario && (
            <>
              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-8">
                <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-3xl">
                    <p className="text-xs font-bold uppercase tracking-widest text-[#10B981] mb-3">Hiring Manager Summary</p>
                    <h1 className="text-3xl lg:text-4xl font-black tracking-tight text-slate-900 dark:text-white">
                      {report.scenarioTitle}
                    </h1>
                    <p className="mt-3 text-sm text-slate-500">
                      Session {sessionId} · Submitted {new Date(submission.timestamp).toLocaleString()}
                    </p>
                    <p className="mt-5 text-base leading-relaxed text-slate-600 dark:text-slate-300">
                      {report.executiveSummary}
                    </p>
                    <div className="mt-6 flex flex-wrap gap-3">
                      <span className={`rounded-full border px-3 py-1.5 text-sm font-bold ${RECOMMENDATION_STYLES[report.recommendation]}`}>
                        {report.recommendation}
                      </span>
                      <span className="rounded-full border border-slate-300 dark:border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-600 dark:text-slate-300">
                        Confidence: {report.confidence}
                      </span>
                      <span className="rounded-full border border-slate-300 dark:border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-600 dark:text-slate-300">
                        Overall Score: {report.overallScore}/100
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 min-w-[280px]">
                    {report.quantMetrics.slice(0, 4).map((metric) => (
                      <MetricTile key={metric.label} label={metric.label} value={metric.value} helper={metric.helper} />
                    ))}
                  </div>
                </div>
              </section>

              <section className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-6">
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Scenario Context</h2>
                  <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{report.scenarioSummary}</p>

                  <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {report.timeline.map((item) => (
                      <div key={item.label} className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{item.label}</p>
                        <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">{item.value}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Decision Signals</h2>
                  <div className="space-y-4">
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Top Strengths</p>
                      <ul className="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
                        {report.strengths.map((item, index) => (
                          <li key={index} className="leading-relaxed">{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Primary Risks</p>
                      <ul className="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
                        {report.risks.map((item, index) => (
                          <li key={index} className="leading-relaxed">{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </section>

              <section>
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Scenario-Specific Capability Signals</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {report.capabilitySignals.map((signal) => (
                    <CapabilityCard
                      key={signal.key}
                      label={signal.label}
                      score={signal.normalizedScore}
                      reasoning={signal.reasoning}
                      weight={signal.weight}
                    />
                  ))}
                </div>
              </section>

              <section>
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Quantified Evaluation Metrics</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {report.quantMetrics.map((metric) => (
                    <MetricTile key={metric.label} label={metric.label} value={metric.value} helper={metric.helper} />
                  ))}
                </div>
              </section>

              <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Candidate Submission</h2>
                  <div className="space-y-5">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Root Cause / Core Recommendation</p>
                      <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{submission.root_cause}</p>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Stakeholder Summary</p>
                      <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{submission.stakeholder_summary}</p>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Proposed Actions</p>
                      <div className="space-y-2">
                        {submission.proposed_actions.map((action, index) => (
                          <div key={`${action.action}-${index}`} className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-3">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="rounded-full bg-[#10B981]/10 px-2 py-0.5 text-[10px] font-bold text-[#10B981]">{action.priority}</span>
                            </div>
                            <p className="text-sm text-slate-700 dark:text-slate-300">{action.action}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Evidence and Investigation Quality</h2>
                  <div className="grid grid-cols-2 gap-4">
                    <MetricTile
                      label="Supporting Evidence"
                      value={report.evidenceInsights.linkedEvidenceCount}
                      helper="Evidence items explicitly linked into the final submission."
                    />
                    <MetricTile
                      label="Annotated Evidence"
                      value={report.evidenceInsights.annotatedEvidenceCount}
                      helper="Saved evidence with candidate-written explanation of why it mattered."
                    />
                    <MetricTile
                      label="Findings Coverage"
                      value={`${report.evidenceInsights.findingsCoverage}%`}
                      helper="Critical scenario findings captured versus missed."
                    />
                    <MetricTile
                      label="Red Herrings"
                      value={report.evidenceInsights.redHerringsEngaged}
                      helper="Misleading signals the candidate spent material effort on."
                    />
                    <MetricTile
                      label="Evidence Linkage"
                      value={`${report.evidenceInsights.evidenceLinkageScore}/100`}
                      helper="How tightly the final case is supported by preserved evidence."
                    />
                    <MetricTile
                      label="Investigation Breadth"
                      value={`${report.decisionInsights.investigationBreadthScore}/100`}
                      helper="Coverage across teammates, evidence, and inquiry depth."
                    />
                  </div>
                </div>
              </section>

              {evidence.length > 0 && (
                <section>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Evidence Appendix</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {evidence.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-bold capitalize">
                            {item.agent.replace(/_/g, " ")}
                          </span>
                          <span className="text-[10px] text-slate-400 uppercase tracking-wider">{item.artifact.kind}</span>
                        </div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{item.artifact.title}</p>
                        <ReviewArtifactView artifact={item.artifact} />
                        {item.annotation && (
                          <div className="mt-3 rounded-lg bg-emerald-500/8 dark:bg-emerald-500/10 border-l-2 border-emerald-500 px-3 py-2">
                            <p className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 mb-0.5">Candidate note</p>
                            <p className="text-xs text-slate-700 dark:text-slate-200 leading-relaxed">{item.annotation}</p>
                          </div>
                        )}
                        <p className="text-[11px] text-slate-400 mt-2">{item.citation.source}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">Investigation Appendix</h2>
                <div className="space-y-3">
                  {queryHistory.slice(-8).reverse().map((query) => (
                    <div key={query.query_log_id} className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-4">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#10B981]">
                          {query.agent.replace(/_/g, " ")}
                        </span>
                        <span className="text-[11px] text-slate-500">{new Date(query.timestamp).toLocaleString()}</span>
                      </div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{query.query}</p>
                      <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400 line-clamp-3">{query.response}</p>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}

          {scoring && (!report || !submission || !scenario) && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 text-amber-100">
              The score exists, but the full assessment report could not be assembled because submission or scenario data is missing.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
