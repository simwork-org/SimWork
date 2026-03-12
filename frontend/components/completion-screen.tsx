"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getHistory, getStatus } from "@/lib/api";
import type { HistoryResponse, SessionStatus } from "@/lib/types";

export function CompletionScreen({ sessionId }: { sessionId: string }) {
  const [history, setHistory] = useState<HistoryResponse>({ queries: [], hypotheses: [], final_submission: null });
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [historyResponse, statusResponse] = await Promise.all([
          getHistory(sessionId),
          getStatus(sessionId)
        ]);
        setHistory(historyResponse);
        setStatus(statusResponse);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load session summary");
      }
    }
    void load();
  }, [sessionId]);

  const durationMinutes = useMemo(() => {
    if (!status?.started_at || !status.completed_at) {
      return 0;
    }
    const started = new Date(status.started_at).getTime();
    const completed = new Date(status.completed_at).getTime();
    return Math.max(1, Math.round((completed - started) / 60000));
  }, [status]);

  async function downloadTranscript() {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${sessionId}-transcript.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-background-dark text-slate-100">
      <div className="layout-container flex h-full grow flex-col">
        <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4 lg:px-20">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-white">
              <span className="material-symbols-outlined text-xl">cognition</span>
            </div>
            <h2 className="text-lg font-bold tracking-tight text-slate-100">SimWork</h2>
          </div>
          <Link
            href="/"
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800 text-slate-400 transition-colors hover:bg-slate-700"
          >
            <span className="material-symbols-outlined">close</span>
          </Link>
        </header>

        <main className="flex flex-1 items-center justify-center px-4 py-12">
          <div className="flex w-full max-w-2xl flex-col items-center">
            <div className="mb-12 flex flex-col items-center gap-6 text-center">
              <div className="relative">
                <div className="absolute inset-0 rounded-full bg-primary/20 blur-3xl" />
                <div className="relative flex h-24 w-24 items-center justify-center rounded-full border-4 border-primary/20 bg-primary/10">
                  <span className="material-symbols-outlined text-5xl font-bold text-primary">check_circle</span>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                <h1 className="text-3xl font-bold tracking-tight text-white">Simulation completed successfully</h1>
                <p className="mx-auto max-w-md text-lg leading-relaxed text-slate-400">
                  Your investigation history has been recorded for evaluation. This MVP stores the full transcript and final submission locally.
                </p>
              </div>
              <div className="flex flex-wrap gap-4">
                <button
                  disabled
                  className="flex h-11 items-center justify-center rounded-lg bg-primary px-6 font-semibold text-white opacity-60"
                >
                  Feedback coming soon
                </button>
                <button
                  onClick={downloadTranscript}
                  className="flex h-11 items-center justify-center rounded-lg bg-slate-800 px-6 font-semibold text-slate-100 transition-colors hover:bg-slate-700"
                >
                  Download Transcript
                </button>
              </div>
            </div>

            <div className="w-full rounded-xl border border-slate-800 bg-slate-900/50 p-8 shadow-sm">
              <h3 className="mb-6 flex items-center gap-2 text-lg font-bold text-white">
                <span className="material-symbols-outlined text-primary">analytics</span>
                Submission Summary
              </h3>

              <div className="grid grid-cols-1 gap-x-12 gap-y-6 md:grid-cols-2">
                <SummaryRow label="Duration" value={`${durationMinutes} minutes`} icon="schedule" />
                <SummaryRow label="Questions" value={`${history.queries.length}`} icon="checklist" />
                <SummaryRow label="Status" value={status?.completed ? "Submitted" : "In progress"} icon="cloud_done" />
                <SummaryRow
                  label="Date"
                  value={status?.completed_at ? new Date(status.completed_at).toLocaleDateString() : "Pending"}
                  icon="event"
                />
              </div>

              <div className="mt-8 space-y-4">
                <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-4">
                  <div className="flex gap-3">
                    <span className="material-symbols-outlined text-primary">info</span>
                    <p className="text-sm leading-relaxed text-slate-400">
                      Final hypothesis: {status?.current_hypothesis ?? "No saved hypothesis."}
                    </p>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-700/50 bg-slate-950/70 p-4">
                  <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Final Summary</p>
                  <p className="mt-3 text-sm leading-relaxed text-slate-300">
                    {history.final_submission?.summary ?? "No final summary captured."}
                  </p>
                </div>
                {error ? <p className="text-sm text-red-400">{error}</p> : null}
              </div>
            </div>

            <div className="mt-12 flex w-full justify-center">
              <Link
                href="/"
                className="flex items-center gap-2 font-medium text-slate-400 transition-colors hover:text-primary"
              >
                <span className="material-symbols-outlined">arrow_back</span>
                Back to Dashboard
              </Link>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  icon
}: {
  label: string;
  value: string;
  icon: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-sm text-slate-500">{icon}</span>
        <p className="text-sm font-medium text-slate-400">{label}</p>
      </div>
      <p className="text-sm font-bold text-slate-100">{value}</p>
    </div>
  );
}
