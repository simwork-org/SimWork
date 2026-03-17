"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthToken } from "@/lib/useAuthToken";
import {
  getSavedEvidence,
  logSessionEvent,
  submitSolution,
  type ProposedAction,
  type SavedEvidence,
} from "@/lib/api";

const PRIORITIES: ProposedAction["priority"][] = ["P0", "P1", "P2"];

function formatCell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString();
  return value;
}

function TablePreview({ item }: { item: SavedEvidence }) {
  if (item.artifact.kind !== "table") return null;
  const columns = item.artifact.columns.slice(0, 4);
  const rows = item.artifact.rows.slice(0, 2);
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700/50">
      <table className="min-w-full text-left text-[11px]">
        <thead className="bg-slate-50 dark:bg-slate-800/40 text-slate-500 uppercase tracking-wide">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-2 py-1.5">{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-slate-200 dark:border-slate-800">
              {columns.map((column) => (
                <td key={`${index}-${column}`} className="px-2 py-1.5 text-slate-700 dark:text-slate-300">
                  {formatCell(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactPreview({ item }: { item: SavedEvidence }) {
  if (item.artifact.kind === "metric") {
    return (
      <div className="rounded-lg border border-slate-200 dark:border-slate-700/50 px-3 py-3 bg-white dark:bg-slate-900/40">
        <p className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-1">Metric</p>
        <p className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          {typeof item.artifact.value === "number" ? item.artifact.value.toLocaleString() : item.artifact.value}
          {item.artifact.unit ? <span className="text-sm text-slate-500 ml-1">{item.artifact.unit}</span> : null}
        </p>
      </div>
    );
  }
  if (item.artifact.kind === "chart") {
    return (
      <div className="rounded-lg border border-slate-200 dark:border-slate-700/50 px-3 py-3 bg-white dark:bg-slate-900/40">
        <p className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-1">{item.artifact.chart_type} chart</p>
        <p className="text-[11px] text-slate-600 dark:text-slate-400">
          {item.artifact.labels.length} labels, {item.artifact.series.length} series
        </p>
      </div>
    );
  }
  return <TablePreview item={item} />;
}

export default function CompletionPage() {
  const params = useParams();
  const router = useRouter();
  useAuthToken();
  const sessionId = params.sessionId as string;

  const [rootCause, setRootCause] = useState("");
  const [proposedActions, setProposedActions] = useState<ProposedAction[]>([
    { action: "", priority: "P0" },
    { action: "", priority: "P1" },
    { action: "", priority: "P2" },
  ]);
  const [stakeholderSummary, setStakeholderSummary] = useState("");
  const [savedEvidence, setSavedEvidence] = useState<SavedEvidence[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<number[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    logSessionEvent(sessionId, "submission_started", {}).catch(() => undefined);
    getSavedEvidence(sessionId).then((data) => setSavedEvidence(data.evidence)).catch(console.error);
  }, [sessionId]);

  const validActions = useMemo(
    () => proposedActions.map((item) => ({ ...item, action: item.action.trim() })).filter((item) => item.action),
    [proposedActions]
  );

  const canSubmit = rootCause.trim().length > 0 && stakeholderSummary.trim().length > 0 && validActions.length > 0 && selectedEvidenceIds.length > 0;

  const toggleEvidence = async (savedEvidenceId: number) => {
    const willSelect = !selectedEvidenceIds.includes(savedEvidenceId);
    setSelectedEvidenceIds((prev) => {
      const next = prev.includes(savedEvidenceId) ? prev.filter((id) => id !== savedEvidenceId) : [...prev, savedEvidenceId];
      return next;
    });
    await logSessionEvent(sessionId, "submission_evidence_selected", {
      saved_evidence_id: savedEvidenceId,
      selected: willSelect,
    }).catch(() => undefined);
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await submitSolution(sessionId, rootCause.trim(), selectedEvidenceIds, validActions, stakeholderSummary.trim());
      setSubmitted(true);
    } catch (error) {
      console.error(error);
    } finally {
      setSubmitting(false);
    }
  };

  if (!submitted) {
    return (
      <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-[#f6f6f8] dark:bg-[#101122]" style={{ fontFamily: "'Inter', sans-serif" }}>
        <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4 lg:px-10 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-[#10B981] text-white">
              <span className="material-symbols-outlined text-xl">cognition</span>
            </div>
            <h2 className="text-slate-900 dark:text-slate-100 text-lg font-bold tracking-tight">SimWork</h2>
          </div>
          <button
            onClick={() => router.push(`/workspace/${sessionId}`)}
            className="rounded-lg h-10 px-4 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-sm font-semibold"
          >
            Back to Investigation
          </button>
        </header>

        <main className="flex flex-1 overflow-hidden">
          <section className="flex-1 overflow-y-auto px-6 py-8 lg:px-10">
            <div className="max-w-3xl space-y-6">
              <div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight mb-2">Submit Your Findings</h1>
                <p className="text-slate-600 dark:text-slate-400">
                  Link your conclusion to the evidence you saved during the investigation.
                </p>
              </div>

              <div className="bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-6 space-y-6">
                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 block">
                    What is the root cause of the conversion drop?
                  </label>
                  <input
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-[#10B981] outline-none"
                    placeholder="State the root cause in one sentence"
                    value={rootCause}
                    onChange={(event) => setRootCause(event.target.value)}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-bold text-slate-700 dark:text-slate-300">Proposed Actions</label>
                    <button
                      onClick={() => setProposedActions((prev) => [...prev, { action: "", priority: "P1" }])}
                      className="text-xs px-2.5 py-1 rounded-full border border-slate-300 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                    >
                      Add action
                    </button>
                  </div>
                  <div className="space-y-3">
                    {proposedActions.map((item, index) => (
                      <div key={index} className="flex gap-3">
                        <select
                          value={item.priority}
                          onChange={(event) =>
                            setProposedActions((prev) => prev.map((current, currentIndex) => currentIndex === index ? { ...current, priority: event.target.value as ProposedAction["priority"] } : current))
                          }
                          className="w-24 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-3 text-sm"
                        >
                          {PRIORITIES.map((priority) => (
                            <option key={priority} value={priority}>{priority}</option>
                          ))}
                        </select>
                        <input
                          className="flex-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#10B981]"
                          placeholder="Action recommendation"
                          value={item.action}
                          onChange={(event) =>
                            setProposedActions((prev) => prev.map((current, currentIndex) => currentIndex === index ? { ...current, action: event.target.value } : current))
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2 block">
                    Brief this to your VP of Product
                  </label>
                  <textarea
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-[#10B981] outline-none min-h-[120px]"
                    placeholder="Write a concise 2-3 sentence stakeholder summary."
                    value={stakeholderSummary}
                    maxLength={500}
                    onChange={(event) => setStakeholderSummary(event.target.value)}
                  />
                  <div className="mt-2 text-right text-[11px] text-slate-500">{stakeholderSummary.length}/500</div>
                </div>

                <button
                  onClick={handleSubmit}
                  disabled={submitting || !canSubmit}
                  className="w-full bg-[#10B981] hover:bg-[#10B981]/90 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                >
                  <span>{submitting ? "Submitting..." : "Submit Final Solution"}</span>
                  <span className="material-symbols-outlined">send</span>
                </button>
              </div>
            </div>
          </section>

          <aside className="w-[420px] border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Supporting Evidence</h3>
              <p className="text-xs text-slate-500 mt-1">Select the saved findings that support your root cause.</p>
            </div>
            <div className="p-4 space-y-3">
              {savedEvidence.length === 0 ? (
                <div className="rounded-xl border border-slate-200 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-800/30 p-4 text-sm text-slate-500">
                  No saved evidence yet. Go back to the workspace and save findings first.
                </div>
              ) : (
                savedEvidence.map((item) => {
                  const selected = selectedEvidenceIds.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className={`block rounded-xl border p-4 cursor-pointer transition-colors ${
                        selected
                          ? "border-emerald-500 bg-emerald-500/5"
                          : "border-slate-200 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-800/30"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleEvidence(item.id)}
                          className="mt-1"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-[12px] font-semibold text-slate-900 dark:text-slate-100">{item.artifact.title}</p>
                          {item.annotation && <p className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">{item.annotation}</p>}
                          <p className="mt-1 text-[11px] text-slate-500">{item.citation.source}</p>
                          <div className="mt-3">
                            <ArtifactPreview item={item} />
                          </div>
                        </div>
                      </div>
                    </label>
                  );
                })
              )}
            </div>
          </aside>
        </main>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-[#f6f6f8] dark:bg-[#101122]" style={{ fontFamily: "'Inter', sans-serif" }}>
      <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-4 lg:px-20 bg-white dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-[#10B981] text-white">
            <span className="material-symbols-outlined text-xl">cognition</span>
          </div>
          <h2 className="text-slate-900 dark:text-slate-100 text-lg font-bold tracking-tight">SimWork</h2>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl bg-white dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-8 shadow-sm">
          <div className="flex flex-col items-center text-center gap-5 mb-8">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[#10B981]/10 border-4 border-[#10B981]/20">
              <span className="material-symbols-outlined text-[#10B981] text-5xl font-bold">check_circle</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">Submission recorded</h1>
              <p className="text-slate-600 dark:text-slate-400 mt-2">Your case has been saved with linked evidence and prioritized actions.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-y-6 gap-x-12">
            <SummaryRow label="Root Cause" value={rootCause} icon="checklist" />
            <SummaryRow label="Evidence Linked" value={String(selectedEvidenceIds.length)} icon="folder_data" />
            <SummaryRow label="Actions Proposed" value={String(validActions.length)} icon="task_alt" />
            <SummaryRow label="Status" value="Submitted" icon="cloud_done" />
          </div>

          <div className="mt-8 flex justify-center">
            <button
              onClick={() => router.push("/")}
              className="flex items-center gap-2 text-slate-500 dark:text-slate-400 hover:text-[#10B981] dark:hover:text-[#10B981] transition-colors font-medium"
            >
              <span className="material-symbols-outlined">arrow_back</span>
              Back to Dashboard
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

function SummaryRow({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-slate-400 text-sm">{icon}</span>
        <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">{label}</p>
      </div>
      <p className="text-slate-900 dark:text-slate-100 text-sm font-bold text-right max-w-[220px] truncate">{value}</p>
    </div>
  );
}
