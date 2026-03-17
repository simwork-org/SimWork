"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useAuthToken } from "@/lib/useAuthToken";
import {
  getSavedEvidence,
  getScoringResult,
  triggerScoring,
  type DimensionScore,
  type SavedEvidence,
  type ScoringResult,
} from "@/lib/api";

const DIMENSION_LABELS: Record<string, string> = {
  root_cause_identification: "Root Cause Identification",
  investigation_methodology: "Investigation Methodology",
  solution_quality: "Solution Quality",
  communication: "Communication",
};

const LEVEL_COLORS: Record<string, string> = {
  excellent: "text-emerald-500",
  good: "text-sky-500",
  adequate: "text-amber-500",
  poor: "text-red-500",
};

const BAR_COLORS: Record<string, string> = {
  excellent: "bg-emerald-500",
  good: "bg-sky-500",
  adequate: "bg-amber-500",
  poor: "bg-red-500",
};

function scoreColor(score: number): string {
  if (score >= 4.5) return "text-emerald-500 border-emerald-500";
  if (score >= 3.5) return "text-sky-500 border-sky-500";
  if (score >= 2.5) return "text-amber-500 border-amber-500";
  return "text-red-500 border-red-500";
}

function ScoreCircle({ score }: { score: number }) {
  return (
    <div className={`flex items-center justify-center size-24 rounded-full border-4 ${scoreColor(score)}`}>
      <span className="text-3xl font-bold">{score.toFixed(1)}</span>
    </div>
  );
}

function DimensionCard({ name, dim }: { name: string; dim: DimensionScore }) {
  const label = DIMENSION_LABELS[name] || name.replace(/_/g, " ");
  const barWidth = `${(dim.score / 5) * 100}%`;
  const barColor = BAR_COLORS[dim.level] || "bg-slate-400";
  const levelColor = LEVEL_COLORS[dim.level] || "text-slate-400";

  return (
    <div className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{label}</h3>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold uppercase ${levelColor}`}>{dim.level}</span>
          <span className="text-lg font-bold text-slate-900 dark:text-slate-100">{dim.score}/5</span>
        </div>
      </div>
      <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full mb-3">
        <div className={`h-2 rounded-full ${barColor} transition-all`} style={{ width: barWidth }} />
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{dim.reasoning}</p>
      <p className="text-[10px] text-slate-400 mt-2">Weight: {(dim.weight * 100).toFixed(0)}%</p>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  return (
    <div className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-lg p-4 text-center">
      <span className="material-symbols-outlined text-slate-400 text-xl mb-1 block">{icon}</span>
      <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      <p className="text-[11px] text-slate-500 mt-1">{label}</p>
    </div>
  );
}

function BulletList({ title, items, icon, color }: { title: string; items: string[]; icon: string; color: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className={`material-symbols-outlined text-sm ${color}`}>{icon}</span>
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h3>
      </div>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={index} className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed pl-4 relative">
            <span className={`absolute left-0 top-1.5 size-1.5 rounded-full ${color.replace("text-", "bg-")}`} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ReviewPage() {
  const params = useParams();
  useAuthToken();
  const sessionId = params.sessionId as string;

  const [scoring, setScoring] = useState<ScoringResult | null>(null);
  const [evidence, setEvidence] = useState<SavedEvidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [scoring_loading, setScoringLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [scoreRes, evidenceRes] = await Promise.allSettled([
          getScoringResult(sessionId),
          getSavedEvidence(sessionId),
        ]);
        if (scoreRes.status === "fulfilled") setScoring(scoreRes.value);
        if (evidenceRes.status === "fulfilled") setEvidence(evidenceRes.value.evidence);
      } catch {
        // Score may not exist yet — that's OK
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

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
          Loading review...
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen w-full flex-col bg-[#f6f6f8] dark:bg-[#101122]" style={{ fontFamily: "'Inter', sans-serif" }}>
      <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4 lg:px-10 bg-white dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-[#10B981] text-white">
            <span className="material-symbols-outlined text-xl">cognition</span>
          </div>
          <h2 className="text-slate-900 dark:text-slate-100 text-lg font-bold tracking-tight">SimWork</h2>
          <span className="text-slate-400 mx-2">/</span>
          <span className="text-slate-500 text-sm font-medium">Candidate Review</span>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-8 lg:px-10">
        <div className="max-w-5xl mx-auto space-y-8">

          {/* No score yet */}
          {!scoring && (
            <div className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-8 text-center">
              <span className="material-symbols-outlined text-4xl text-slate-300 dark:text-slate-600 mb-4 block">grading</span>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Score not yet generated</h2>
              <p className="text-sm text-slate-500 mb-6">
                Generate an AI-powered evaluation of this candidate&apos;s investigation and submission.
              </p>
              {error && (
                <p className="text-sm text-red-500 mb-4">{error}</p>
              )}
              <button
                onClick={handleGenerateScore}
                disabled={scoring_loading}
                className="inline-flex items-center gap-2 bg-[#10B981] hover:bg-[#10B981]/90 text-white font-bold py-3 px-6 rounded-xl transition-all disabled:opacity-50"
              >
                {scoring_loading ? (
                  <>
                    <span className="material-symbols-outlined animate-spin text-sm">progress_activity</span>
                    Scoring...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">auto_awesome</span>
                    Generate Score
                  </>
                )}
              </button>
            </div>
          )}

          {/* Scoring results */}
          {scoring && (
            <>
              {/* Header with overall score */}
              <div className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-8 flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight mb-1">Candidate Evaluation</h1>
                  <p className="text-sm text-slate-500">
                    Session: {sessionId}
                    {scoring.scored_at && ` · Scored: ${new Date(scoring.scored_at).toLocaleDateString()}`}
                  </p>
                </div>
                <ScoreCircle score={scoring.overall_score} />
              </div>

              {/* Dimension scores */}
              <section>
                <h2 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 uppercase tracking-wide">Dimension Scores</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(scoring.dimensions).map(([name, dim]) => (
                    <DimensionCard key={name} name={name} dim={dim} />
                  ))}
                </div>
              </section>

              {/* Process signals */}
              <section>
                <h2 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 uppercase tracking-wide">Investigation Process</h2>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <StatCard label="Total Queries" value={scoring.process_signals.total_queries} icon="forum" />
                  <StatCard label="Evidence Saved" value={scoring.process_signals.evidence_saved_count} icon="bookmark" />
                  <StatCard label="Agents Used" value={Object.keys(scoring.process_signals.agents_used).length} icon="groups" />
                  <StatCard
                    label="Typed / Suggested"
                    value={`${scoring.process_signals.typed_vs_suggestion.typed}/${scoring.process_signals.typed_vs_suggestion.suggestion}`}
                    icon="keyboard"
                  />
                  <StatCard label="Duration (min)" value={scoring.process_signals.session_duration_minutes} icon="timer" />
                </div>

                {/* Agent breakdown */}
                <div className="mt-4 bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-5">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Agent Query Distribution</h3>
                  <div className="flex gap-6">
                    {Object.entries(scoring.process_signals.agents_used).map(([agent, count]) => (
                      <div key={agent} className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 capitalize">{agent.replace(/_/g, " ")}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-bold">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              {/* Highlights / Missed / Red Herrings */}
              <section>
                <h2 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 uppercase tracking-wide">Key Signals</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-6">
                  <BulletList title="Highlights" items={scoring.highlights} icon="check_circle" color="text-emerald-500" />
                  <BulletList title="Missed Signals" items={scoring.missed_signals} icon="warning" color="text-amber-500" />
                  <BulletList title="Red Herrings Engaged" items={scoring.red_herrings_engaged} icon="nearby_error" color="text-red-400" />
                </div>
              </section>

              {/* Saved evidence */}
              {evidence.length > 0 && (
                <section>
                  <h2 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 uppercase tracking-wide">
                    Candidate&apos;s Saved Evidence ({evidence.length} items)
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {evidence.map((item) => (
                      <div key={item.id} className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-bold capitalize">
                            {item.agent.replace(/_/g, " ")}
                          </span>
                          <span className="text-[10px] text-slate-400">{item.artifact.kind}</span>
                        </div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{item.artifact.title}</p>
                        {item.annotation && (
                          <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">{item.annotation}</p>
                        )}
                        <p className="text-[11px] text-slate-400 mt-1">{item.citation.source}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
